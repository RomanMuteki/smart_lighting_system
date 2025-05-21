from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import json
import csv
import os
import time
import threading

app = FastAPI()

log_file = "event_log.csv"
if not os.path.exists(log_file):
    with open(log_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "event_type", "object_id", "details"])


def log_event_csv(event_type, object_id, details):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(log_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, event_type, object_id, details])

# Хранилища
lamps_status = {}
broken_cameras = set()
current_time = 0


# Загрузка графа из Json
def load_graph_from_json(filename="graph.json"):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        cameras = data.get("cameras", [])
        edges = data.get("edges", [])
        graph = {cam: {"incoming_edges": [], "outgoing_edges": []} for cam in cameras}
        for start_id, end_id in edges:
            graph[start_id]["outgoing_edges"].append(end_id)
            graph[end_id]["incoming_edges"].append(start_id)
        return graph, edges
    except:
        return {}, []

original_graph, initial_edges = load_graph_from_json()
graph = {cam: {
    "incoming_edges": original_graph[cam]["incoming_edges"].copy(),
    "outgoing_edges": original_graph[cam]["outgoing_edges"].copy()
} for cam in original_graph}

for start_id, end_id in initial_edges:
    lamp_id = f"{start_id}→{end_id}"
    lamps_status[lamp_id] = {
        "status": "OFF",
        "car_count": 0,
        "broken": False,
        "last_updated": "Not updated",
        "receive_time": 0
    }


def is_edge_broken(start_id, end_id):
    return start_id in broken_cameras or end_id in broken_cameras


def update_time():
    global current_time
    start = time.time()
    while True:
        current_time = time.time() - start
        time.sleep(0.01)

threading.Thread(target=update_time, daemon=True).start()


# Модели запроса
class LampUpdate(BaseModel):
    lamp_id: int
    prev_lamp_ids: Optional[List[int]] = []
    set_broken: Optional[bool] = None

@app.get("/status")
def get_status():
    return {
        "lamps": lamps_status,
        "graph": graph,
        "broken_cameras": list(broken_cameras)
    }

@app.post("/")
def update_lamp(data: LampUpdate):
    lamp_id = data.lamp_id
    set_broken = data.set_broken
    prev_lamp_ids = data.prev_lamp_ids or []

    if lamp_id not in graph:
        return JSONResponse(content={"error": "Invalid camera ID"}, status_code=400)

    if set_broken is not None:
        if set_broken:
            broken_cameras.add(lamp_id)
            log_event_csv("camera_broken", lamp_id, "Камера помечена как сломанная")

            in_edges = graph[lamp_id]["incoming_edges"].copy()
            out_edges = graph[lamp_id]["outgoing_edges"].copy()
            for edge_id in list(lamps_status.keys()):
                s, e = map(int, edge_id.split("→"))
                if s == lamp_id or e == lamp_id:
                    if lamps_status[edge_id]["status"] != "OFF":
                        log_event_csv("lamp_off", edge_id, "Фонарь выключен (нет машин)")
                    lamps_status[edge_id]["broken"] = True
                    lamps_status[edge_id]["status"] = "OFF"
                    lamps_status[edge_id]["car_count"] = 0
                    lamps_status[edge_id]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            for s in in_edges:
                for e in out_edges:
                    new_id = f"{s}→{e}"
                    if new_id not in lamps_status:
                        prev_id = f"{s}→{lamp_id}"
                        car_count = lamps_status.get(prev_id, {}).get("car_count", 0)
                        lamps_status[new_id] = {
                            "status": "ON" if car_count > 0 else "OFF",
                            "car_count": car_count,
                            "broken": is_edge_broken(s, e),
                            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "receive_time": current_time
                        }
                        graph[s]["outgoing_edges"].append(e)
                        graph[e]["incoming_edges"].append(s)
            graph[lamp_id]["incoming_edges"] = []
            graph[lamp_id]["outgoing_edges"] = []
        else:
            broken_cameras.discard(lamp_id)
            log_event_csv("camera_restored", lamp_id, "Камера восстановлена")

            for s in original_graph[lamp_id]["incoming_edges"]:
                for e in original_graph[lamp_id]["outgoing_edges"]:
                    lamps_status.pop(f"{s}→{e}", None)
            for lid in lamps_status:
                s, e = map(int, lid.split("→"))
                lamps_status[lid]["broken"] = is_edge_broken(s, e)
            for cam in graph:
                graph[cam]["incoming_edges"] = original_graph[cam]["incoming_edges"].copy()
                graph[cam]["outgoing_edges"] = original_graph[cam]["outgoing_edges"].copy()
        return {"message": f"Камера {lamp_id} {'помечена как сломанная' if set_broken else 'восстановлена'}"}

    log_event_csv("car_detected", lamp_id, "Автомобиль обнаружен камерой")

    for next_id in graph[lamp_id]["outgoing_edges"]:
        edge_id = f"{lamp_id}→{next_id}"
        if edge_id in lamps_status and not lamps_status[edge_id]["broken"]:
            lamps_status[edge_id]["car_count"] += 1
            lamps_status[edge_id]["status"] = "ON"
            lamps_status[edge_id]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            lamps_status[edge_id]["receive_time"] = current_time

    for prev_id in prev_lamp_ids:
        if prev_id in graph and prev_id not in broken_cameras:
            for next_id in graph[prev_id]["outgoing_edges"]:
                edge_id = f"{prev_id}→{next_id}"
                if edge_id in lamps_status and not lamps_status[edge_id]["broken"]:
                    lamps_status[edge_id]["car_count"] = max(0, lamps_status[edge_id]["car_count"] - 1)
                    if lamps_status[edge_id]["car_count"] == 0:
                        lamps_status[edge_id]["status"] = "OFF"
                        lamps_status[edge_id]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

    return {"message": "Данные приняты", "current_time": round(current_time, 2)}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='localhost', port=8080)