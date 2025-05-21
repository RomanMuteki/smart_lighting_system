import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import csv
import os

log_file = "event_log.csv"

# Если файла нет — создаём с заголовками
if not os.path.exists(log_file):
    with open(log_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "event_type", "object_id", "details"])

def log_event_csv(event_type, object_id, details):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(log_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, event_type, object_id, details])


# Инициализация хранилища фонарей (ребер)
lamps_status = {}

# Загрузка графа из JSON-файла
def load_graph_from_json(filename="graph.json"):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        cameras = data.get("cameras", [])
        edges = data.get("edges", [])
        # Инициализация графа
        graph = {cam: {"incoming_edges": [], "outgoing_edges": []} for cam in cameras}
        for start_id, end_id in edges:
            if start_id in graph and end_id in graph:
                graph[start_id]["outgoing_edges"].append(end_id)
                graph[end_id]["incoming_edges"].append(start_id)
        return graph, edges
    except FileNotFoundError:
        print(f"Ошибка: Файл {filename} не найден")
        return {}, []
    except json.JSONDecodeError:
        print(f"Ошибка: Неверный формат JSON в {filename}")
        return {}, []

# Исходный и текущий граф
original_graph, initial_edges = load_graph_from_json()
graph = {cam: {
    "incoming_edges": original_graph[cam]["incoming_edges"].copy(),
    "outgoing_edges": original_graph[cam]["outgoing_edges"].copy()
} for cam in original_graph}

# Инициализация фонарей (ребер)
for start_id, end_id in initial_edges:
    lamp_id = f"{start_id}→{end_id}"
    lamps_status[lamp_id] = {
        "status": "OFF",
        "car_count": 0,
        "broken": False,
        "last_updated": "Not updated",
        "receive_time": 0
    }

# Список сломанных камер
broken_cameras = set()

current_time = 0

def update_time():
    global current_time
    start_time = time.time()
    while True:
        current_time = time.time() - start_time
        time.sleep(0.01)

def update_lamp_status():
    while True:
        try:
            status_output = []
            for lamp_id, data in lamps_status.items():
                status_output.append(f"Фонарь #{lamp_id}: {data['status']}, Авто: {data['car_count']}, Сломана: {data['broken']}")

            #print("Текущее состояние фонарей: " + ", ".join(status_output))
        except Exception as e:
            print(f"Ошибка в update_lamp_status: {e}")
        time.sleep(1)

def is_edge_broken(start_id, end_id):
    """Проверяет, сломано ли ребро (если одна из камер сломана)."""
    return start_id in broken_cameras or end_id in broken_cameras

class LampRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        if not post_data:
            self.send_error(400, "Empty data")
            return

        try:
            data = json.loads(post_data)
            lamp_id = data.get('lamp_id')  # ID камеры
            prev_lamp_ids = data.get('prev_lamp_ids', [])  # Список предыдущих камер
            set_broken = data.get('set_broken', None)

            if lamp_id is None:
                self.send_error(400, "Missing required field: lamp_id")
                return

            # Обработка поломки или восстановления камеры
            if set_broken is not None and lamp_id in graph:
                if set_broken:
                    # Поломка камеры
                    broken_cameras.add(lamp_id)
                    log_event_csv("camera_broken", lamp_id, "Камера помечена как сломанная")


                    incoming_edges = graph[lamp_id]["incoming_edges"].copy()
                    outgoing_edges = graph[lamp_id]["outgoing_edges"].copy()
                    # Отключаем связанные ребра
                    for edge_lamp_id in list(lamps_status.keys()):
                        start_id, end_id = map(int, edge_lamp_id.split('→'))
                        if start_id == lamp_id or end_id == lamp_id:
                            lamps_status[edge_lamp_id]["broken"] = True
                            lamps_status[edge_lamp_id]["status"] = "OFF"
                            lamps_status[edge_lamp_id]["car_count"] = 0
                            lamps_status[edge_lamp_id]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                            if lamps_status[edge_lamp_id]["status"] != "ON":
                                log_event_csv("lamp_on", edge_lamp_id, "Фонарь включён")
                            if lamps_status[edge_lamp_id]["status"] != "OFF":
                                log_event_csv("lamp_off", edge_lamp_id, "Фонарь выключен (нет машин)")
                    # Создаем объединенные ребра
                    for start_id in incoming_edges:
                        for end_id in outgoing_edges:
                            new_lamp_id = f"{start_id}→{end_id}"
                            if new_lamp_id not in lamps_status:
                                # Переносим car_count из входящего ребра
                                prev_lamp_id = f"{start_id}→{lamp_id}"
                                car_count = lamps_status.get(prev_lamp_id, {"car_count": 0})["car_count"]
                                lamps_status[new_lamp_id] = {
                                    "status": "ON" if car_count > 0 else "OFF",
                                    "car_count": car_count,
                                    "broken": is_edge_broken(start_id, end_id),
                                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                                    "receive_time": current_time
                                }
                                # Обновляем граф
                                if start_id in graph and end_id in graph:
                                    graph[start_id]["outgoing_edges"].append(end_id)
                                    graph[end_id]["incoming_edges"].append(start_id)
                    # Удаляем старые ребра из графа
                    graph[lamp_id]["incoming_edges"] = []
                    graph[lamp_id]["outgoing_edges"] = []
                    for start_id in incoming_edges:
                        if lamp_id in graph[start_id]["outgoing_edges"]:
                            graph[start_id]["outgoing_edges"].remove(lamp_id)
                    for end_id in outgoing_edges:
                        if lamp_id in graph[end_id]["incoming_edges"]:
                            graph[end_id]["incoming_edges"].remove(lamp_id)
                    action = "сломанной"
                else:
                    # Восстановление камеры
                    broken_cameras.discard(lamp_id)
                    log_event_csv("camera_restored", lamp_id, "Камера восстановлена")

                    # Удаляем объединенные ребра
                    incoming_edges = original_graph[lamp_id]["incoming_edges"]
                    outgoing_edges = original_graph[lamp_id]["outgoing_edges"]
                    for start_id in incoming_edges:
                        for end_id in outgoing_edges:
                            new_lamp_id = f"{start_id}→{end_id}"
                            if new_lamp_id in lamps_status:
                                del lamps_status[new_lamp_id]
                    # Восстанавливаем исходные ребра
                    for edge_lamp_id in lamps_status:
                        start_id, end_id = map(int, edge_lamp_id.split('→'))
                        lamps_status[edge_lamp_id]["broken"] = is_edge_broken(start_id, end_id)
                    # Восстанавливаем граф
                    for cam_id in graph:
                        graph[cam_id]["incoming_edges"] = original_graph[cam_id]["incoming_edges"].copy()
                        graph[cam_id]["outgoing_edges"] = original_graph[cam_id]["outgoing_edges"].copy()
                    action = "восстановленной"
                response = {"message": f"Камера {lamp_id} помечена как {action}"}
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                return

            # Обработка проезда автомобиля
            if lamp_id not in graph or lamp_id in broken_cameras:
                self.send_error(400, "Camera is broken or invalid")
                return

            log_event_csv("car_detected", lamp_id, "Автомобиль обнаружен камерой")

            # Увеличиваем car_count для исходящих ребер текущей камеры
            for next_id in graph[lamp_id]["outgoing_edges"]:
                edge_lamp_id = f"{lamp_id}→{next_id}"
                if edge_lamp_id in lamps_status and not lamps_status[edge_lamp_id]["broken"]:
                    lamps_status[edge_lamp_id]["car_count"] += 1
                    lamps_status[edge_lamp_id]["status"] = "ON"
                    lamps_status[edge_lamp_id]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    lamps_status[edge_lamp_id]["receive_time"] = current_time

            # Уменьшаем car_count для исходящих ребер предыдущих камер
            for prev_id in prev_lamp_ids:
                if prev_id in graph and prev_id not in broken_cameras:
                    for next_id in graph[prev_id]["outgoing_edges"]:
                        edge_lamp_id = f"{prev_id}→{next_id}"
                        if edge_lamp_id in lamps_status and not lamps_status[edge_lamp_id]["broken"]:
                            lamps_status[edge_lamp_id]["car_count"] = max(0, lamps_status[edge_lamp_id]["car_count"] - 1)
                            if lamps_status[edge_lamp_id]["car_count"] == 0:
                                lamps_status[edge_lamp_id]["status"] = "OFF"
                                lamps_status[edge_lamp_id]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            response = {
                "message": "Данные приняты",
                "current_time": round(current_time, 2)
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")

    def do_GET(self):
        if self.path == '/status':
            try:
                response = {
                    "lamps": lamps_status,
                    "graph": graph,
                    "broken_cameras": list(broken_cameras)
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_error(500, f"Internal server error: {str(e)}")
        else:
            self.send_error(405, "Only /status endpoint is supported")

def run_server(port=8080):
    if not original_graph:
        print("Ошибка: Граф не загружен. Сервер не запускается.")
        return
    server_address = ('', port)
    httpd = HTTPServer(server_address, LampRequestHandler)
    print(f"Сервер запущен на порту {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    time_thread = threading.Thread(target=update_time, daemon=True)
    status_thread = threading.Thread(target=update_lamp_status, daemon=True)

    print("Запуск потоков...")
    time_thread.start()
    status_thread.start()

    run_server()
