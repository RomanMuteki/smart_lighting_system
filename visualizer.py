import tkinter as tk
from tkinter import ttk
import math
import requests
import random
import threading


server_url = 'http://localhost:8080'
vertices = []
edges = []
vertex_counter = 0

def connect_to_server():
    global vertex_counter, vertices, edges
    print("Вызвана функция connect_to_server")
    vertices.clear()
    edges.clear()
    vertex_counter = 0
    try:
        # Получение информации с сервера
        response = requests.get(f"{server_url}/status", timeout=2)
        if response.status_code != 200:
            raise Exception("Не удалось получить граф с сервера")
        data = response.json()
        graph = data["graph"]

        # Создание камер
        x = 100
        y = 100
        for cam_id in graph:
            if int(cam_id) < 9:
                print(f"Рисуем камеру {cam_id}")
                draw_camera(x=x, y=y, vindex=int(cam_id), cam_status='Good')
                x += 60
                y += 20 + random.randint(-20,30)

        draw_camera(x=220, y=50, vindex=9, cam_status='Good')
        draw_camera(x=220, y=260, vindex=10, cam_status='Good')
        draw_camera(x=220, y=20, vindex=13, cam_status='Good')
        draw_camera(x=280, y=290, vindex=11, cam_status='Good')
        draw_camera(x=340, y=280, vindex=12, cam_status='Good')

        # Создание рёбер
        for cam_id in graph:
            for end_id in graph[cam_id]["outgoing_edges"]:
                start_vertex = next((v for v in vertices if v['id'] == int(cam_id)), None)
                end_vertex = next((v for v in vertices if v['id'] == end_id), None)
                if start_vertex and end_vertex:
                    print(f"Рисуем ребро между камерами {cam_id} и {end_id}")
                    edge_id = draw_edge(start_vertex, end_vertex, edge_status=False)
                    if edge_id:
                        edges.append({
                            "start_id": int(cam_id),
                            "end_id": end_id,
                            "canvas_id": edge_id,
                            "lamp_id": f"{cam_id}→{end_id}"
                        })

        status_.set("Граф создан, ожидание подключения")
        statusL.config(foreground='orange')
        threaded_update_lamp_status()
    except Exception as e:
        print(f"Ошибка в connect_to_server: {e}")
        status_.set("Ошибка создания графа")
        statusL.config(foreground='red')


# Отрисовка камер
def draw_camera(cam_id=None, cam_status=None, x=None, y=None, vindex=None):
    global vertex_counter, vertices
    min_dist = 30

    if vindex is not None:
        vertex_id = vindex
    else:
        for vertex in vertices:
            distance = math.sqrt((x - vertex['x']) ** 2 + (y - vertex['y']) ** 2)
            if distance < min_dist:
                print(f"Пропущена вершина: слишком близко к x={x}, y={y}")
                return
        vertex_counter += 1
        vertex_id = vertex_counter

    vertex = {'id': vertex_id, 'x': x, 'y': y}
    print(f"Создаём вершину id={vertex_id}, x={x}, y={y}, status={cam_status}")

    if cam_status == 'Good':
        vertex_round_id = canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill='green', outline='yellow')
    else:
        vertex_round_id = canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill='red', outline='yellow')

    vertex['rid'] = vertex_round_id
    for i, v in enumerate(vertices):
        if v['id'] == vertex_id:
            vertices[i] = vertex
            break
    else:
        vertices.append(vertex)


# Отрисовка рёбер
def draw_edge(start_vertex, end_vertex, event=None, edge_status=None):
    radius = 6
    x_size = end_vertex['x'] - start_vertex['x']
    y_size = end_vertex['y'] - start_vertex['y']
    distance = math.sqrt(x_size ** 2 + y_size ** 2)
    if distance == 0:
        print("Ребро не создано: вершины совпадают")
        return None

    x_size /= distance
    y_size /= distance
    start_x = start_vertex['x'] + x_size * radius
    start_y = start_vertex['y'] + y_size * radius
    end_x = end_vertex['x'] - x_size * radius
    end_y = end_vertex['y'] - y_size * radius

    try:
        if edge_status is False:
            edge_id = canvas.create_line(start_x, start_y, end_x, end_y, arrow=tk.LAST, fill="black", width=1,
                                        arrowshape=(3, 3, 2), smooth=True, joinstyle='round')
        else:
            edge_id = canvas.create_line(start_x, start_y, end_x, end_y, arrow=tk.LAST, fill="lightskyblue", width=1,
                                        arrowshape=(3, 3, 2), smooth=True, joinstyle='round')
        print(f"Создано ребро от id={start_vertex['id']} к id={end_vertex['id']}")
        return edge_id
    except Exception as e:
        print(f"Ошибка при создании ребра: {e}")
        return None


# Запрос на сервер о статусе рёбер и вершин
def update_lamp_status():
    try:
        response = requests.get(f"{server_url}/status", timeout=2)
        if response.status_code == 200:
            data = response.json()
            lamp_data = data["lamps"]
            broken_cameras = set(data["broken_cameras"])

            # Обновление цвета камер
            for vertex in vertices:
                lamp_id = vertex['id']
                if lamp_id in broken_cameras:
                    canvas.itemconfig(vertex['rid'], fill='red')
                else:
                    has_active_lamp = False
                    for edge in edges:
                        if edge["start_id"] == lamp_id and edge["lamp_id"] in lamp_data and lamp_data[edge["lamp_id"]]["car_count"] > 0:
                            has_active_lamp = True
                            break
                    canvas.itemconfig(vertex['rid'], fill='yellow' if has_active_lamp else 'green')

            # Обновление статусов рёбер
            for edge in edges:
                canvas_id = edge["canvas_id"]
                lamp_id = edge["lamp_id"]
                has_cars = lamp_id in lamp_data and lamp_data[lamp_id]["car_count"] > 0 and not lamp_data[lamp_id]["broken"]
                canvas.itemconfig(canvas_id, fill="lightskyblue" if has_cars else "black")
            status_.set(f"Подключено, фонарей: {len(lamp_data)}")
            statusL.config(foreground='green')
        else:
            status_.set("Ошибка подключения")
            statusL.config(foreground='red')
    except requests.RequestException:
        status_.set("Сервер недоступен")
        statusL.config(foreground='red')
    root.after(1000, threaded_update_lamp_status)


def threaded_update_lamp_status():
    threading.Thread(target=update_lamp_status, daemon=True).start()


# Нажатие ЛКМ на камеру имитирует обнаружение автомобиля
def find_car(event=None):
    def send_car_event(lamp_id, prev_lamp_ids):
        try:
            data = {"lamp_id": lamp_id, "prev_lamp_ids": prev_lamp_ids}
            response = requests.post(server_url, json=data, timeout=2)
            if response.status_code != 200:
                status_.set("Ошибка отправки на сервер")
                statusL.config(foreground='red')
        except requests.RequestException:
            status_.set("Ошибка отправки на сервер")
            statusL.config(foreground='red')


    x, y = event.x, event.y
    for vertex in vertices:
        distance = math.sqrt((x - vertex['x'])**2 + (y - vertex['y'])**2)
        if distance < 7:
            lamp_id = vertex['id']
            response = requests.get(f"{server_url}/status", timeout=2)
            if response.status_code == 200 and lamp_id in response.json()["broken_cameras"]:
                print(f"Камера {lamp_id} сломана, игнорируем клик")
                return
            data = response.json()
            graph = data["graph"]
            prev_lamp_ids = []
            if str(lamp_id) in graph:
                for prev_id in graph[str(lamp_id)]["incoming_edges"]:
                    if int(prev_id) not in data["broken_cameras"]:
                        prev_lamp_ids.append(prev_id)
            data = {
                "lamp_id": lamp_id,
                "prev_lamp_ids": prev_lamp_ids
            }
            threading.Thread(target=send_car_event, args=(lamp_id, prev_lamp_ids), daemon=True).start()

def break_camera(event=None):
    def toggle_camera_broken(lamp_id, set_broken):
        try:
            response = requests.post(server_url, json={"lamp_id": lamp_id, "set_broken": set_broken}, timeout=2)
            if response.status_code != 200:
                print(f"Ошибка при {'восстановлении' if not set_broken else 'пометке'} камеры {lamp_id}")
                return
        except requests.RequestException as e:
            print(f"Ошибка связи с сервером: {e}")


    x, y = event.x, event.y
    for vertex in vertices:
        distance = math.sqrt((x - vertex['x'])**2 + (y - vertex['y'])**2)
        if distance < 7:
            lamp_id = vertex['id']
            response = requests.get(f"{server_url}/status", timeout=2)
            if response.status_code != 200:
                print(f"Ошибка связи с сервером при проверке камеры {lamp_id}")
                return
            data = threading.Thread(target=toggle_camera_broken, args=(lamp_id, True), daemon=True).start()
            is_broken = lamp_id in data["broken_cameras"]

            if is_broken:

                # Восстановление камеры
                print(f"Восстанавливаем камеру id={lamp_id}")
                try:
                    response = threading.Thread(target=toggle_camera_broken, args=(lamp_id, False), daemon=True).start()
                    if response.status_code != 200:
                        print(f"Ошибка при восстановлении камеры {lamp_id}")
                        return
                except requests.RequestException as e:
                    print(f"Ошибка связи с сервером: {e}")
                    return
                canvas.delete(vertex['rid'])
                x, y = vertex['x'], vertex['y']
                draw_camera(x=x, y=y, vindex=lamp_id, cam_status='Good')

                # Удаление побочных рёбер, созданных при поломке камеры
                new_edges = []
                for edge in edges:
                    if edge["lamp_id"] in [f"{start_id}→{end_id}" for start_id in data["graph"][str(lamp_id)]["incoming_edges"]
                                          for end_id in data["graph"][str(lamp_id)]["outgoing_edges"]]:
                        canvas.delete(edge["canvas_id"])
                    else:
                        new_edges.append(edge)
                edges.clear()
                edges.extend(new_edges)

                # Восстановление исходны рёбер
                if str(lamp_id) in data["graph"]:
                    for end_id in data["graph"][str(lamp_id)]["outgoing_edges"]:
                        start_vertex = next((v for v in vertices if v['id'] == lamp_id), None)
                        end_vertex = next((v for v in vertices if v['id'] == end_id), None)
                        if start_vertex and end_vertex:
                            print(f"Восстанавливаем ребро от {lamp_id} к {end_id}")
                            edge_id = draw_edge(start_vertex, end_vertex, edge_status=False)
                            if edge_id:
                                edges.append({
                                    "start_id": lamp_id,
                                    "end_id": end_id,
                                    "canvas_id": edge_id,
                                    "lamp_id": f"{lamp_id}→{end_id}"
                                })
                    for start_id in data["graph"][str(lamp_id)]["incoming_edges"]:
                        start_vertex = next((v for v in vertices if v['id'] == start_id), None)
                        end_vertex = next((v for v in vertices if v['id'] == lamp_id), None)
                        if start_vertex and end_vertex:
                            print(f"Восстанавливаем ребро от {start_id} к {lamp_id}")
                            edge_id = draw_edge(start_vertex, end_vertex, edge_status=False)
                            if edge_id:
                                edges.append({
                                    "start_id": start_id,
                                    "end_id": lamp_id,
                                    "canvas_id": edge_id,
                                    "lamp_id": f"{start_id}→{lamp_id}"
                                })
            else:
                # Поломка камеры
                print(f"Помечаем камеру id={lamp_id} как неисправную")
                try:
                    response = requests.post(server_url, json={"lamp_id": lamp_id, "set_broken": True}, timeout=2)
                    if response.status_code != 200:
                        print(f"Ошибка при пометке камеры {lamp_id} как сломанной")
                        return
                except requests.RequestException as e:
                    print(f"Ошибка связи с сервером: {e}")
                    return
                canvas.delete(vertex['rid'])
                x, y = vertex['x'], vertex['y']
                draw_camera(x=x, y=y, vindex=lamp_id, cam_status='Bad')

                # Удаление рёбер, которые были связаны со сломанной камерой
                new_edges = []
                for edge in edges:
                    if edge["start_id"] == lamp_id or edge["end_id"] == lamp_id:
                        canvas.delete(edge["canvas_id"])
                    else:
                        new_edges.append(edge)
                edges.clear()
                edges.extend(new_edges)

                # Создание объединённых рёбер
                if str(lamp_id) in data["graph"]:
                    for start_id in data["graph"][str(lamp_id)]["incoming_edges"]:
                        for end_id in data["graph"][str(lamp_id)]["outgoing_edges"]:
                            start_vertex = next((v for v in vertices if v['id'] == start_id), None)
                            end_vertex = next((v for v in vertices if v['id'] == end_id), None)
                            if start_vertex and end_vertex:
                                print(f"Создаем новое ребро от {start_id} к {end_id}")
                                edge_id = draw_edge(start_vertex, end_vertex, edge_status=False)
                                if edge_id:
                                    edges.append({
                                        "start_id": start_id,
                                        "end_id": end_id,
                                        "canvas_id": edge_id,
                                        "lamp_id": f"{start_id}→{end_id}"
                                    })

if __name__ == "__main__":
    root = tk.Tk()
    root.title('Smart Light Visualizer')
    root.geometry('650x800')
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=1)

    root.bind('<Up>', lambda event: threading.Thread(target=connect_to_server, daemon=True).start())

    main_frame = ttk.Frame(root)
    main_frame.grid(column=0, row=0, columnspan=2)
    main_frame.grid_rowconfigure(0, weight=1)
    main_frame.grid_rowconfigure(1, weight=15)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)
    main_frame.grid_columnconfigure(2, weight=1)

    bt1 = ttk.Label(main_frame, text='ЛКМ по камере - обнаружить машину |')
    bt1.grid(column=0, row=0)
    bt2 = ttk.Label(main_frame, text='ПКМ по камере - изобразить выход из строя |')
    bt2.grid(column=1, row=0)

    status_ = tk.StringVar(value='Ожидание подключения')
    statusL = ttk.Label(main_frame, textvariable=status_, foreground='orange')
    statusL.grid(column=2, row=0)

    canvas = tk.Canvas(height=600, width=800, bg='white')
    canvas.bind('<Button-1>', find_car)
    canvas.bind('Alt-Button-1', find_car)
    canvas.bind('<Button-3>', break_camera)
    canvas.grid(column=0, row=1, sticky='nsew', columnspan=3)

    root.mainloop()
