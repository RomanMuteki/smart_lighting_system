import tkinter as tk
from tkinter import ttk
import math

#todo Взаимодействие с сервером, когда тот будет готов

vertices = []
edges = []
action_stack = []
deleted_vertices = []
vertex_counter = 0
counter = 0


def connect_to_server():
    # todo Тут будет отправка на сервер
    global vertex_counter, deleted_vertices, vertices
    x = 100
    y = 100
    for i in range(8):
        draw_camera(x=x+i*50, y=y+i*15, cam_status='Good')

    for i in range(0, 7):
        draw_edge(vertices[i], vertices[i+1], edge_status=False)


def draw_camera(cam_id=None, cam_status=None, x=None, y=None, vindex=None):
    global vertex_counter, deleted_vertices, vertices
    min_dist = 15

    if vindex is not None:
        vertex_id = vindex
    else:
        for vertex in vertices:
            distance = math.sqrt((x - vertex['x']) ** 2 + (y - vertex['y']) ** 2)
            if distance < min_dist:
                return
        vertex_counter += 1
        vertex_id = vertex_counter

    vertex = {'id': vertex_id, 'x': x, 'y': y}

    if cam_status == 'Good':
        vertex_round_id = canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill='green', outline='yellow')
    else:
        vertex_round_id = canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill='red', outline='yellow')

    vertex['rid'] = vertex_round_id

    # ⬇ Добавляем или заменяем вершину
    for i, v in enumerate(vertices):
        if v['id'] == vertex_id:
            vertices[i] = vertex
            break
    else:
        vertices.append(vertex)


def draw_edge(start_vertex, end_vertex, event=None, edge_status=None):
        radius = 6

        x_size = end_vertex['x'] - start_vertex['x']
        y_size = end_vertex['y'] - start_vertex['y']
        distance = math.sqrt(x_size ** 2 + y_size ** 2)
        if distance == 0:
            return None

        x_size /= distance
        y_size /= distance

        start_x = start_vertex['x'] + x_size * radius
        start_y = start_vertex['y'] + y_size * radius
        end_x = end_vertex['x'] - x_size * radius
        end_y = end_vertex['y'] - y_size * radius

        if edge_status == False:
            edge_id = canvas.create_line(start_x, start_y, end_x, end_y, arrow=tk.LAST, fill="black", width=1,
                                         arrowshape=(3, 3, 2), smooth=True, joinstyle='round')
        else:
            edge_id = canvas.create_line(start_x, start_y, end_x, end_y, arrow=tk.LAST, fill="lightskyblue", width=1,
                                         arrowshape=(3, 3, 2), smooth=True, joinstyle='round')
        return edge_id


def ph():
    pass


def find_car(event=None, X=None, Y=None):
    #todo Тут будет отправка на сервер
    x, y = event.x, event.y
    for vertex in vertices:
        distance = math.sqrt((x - vertex['x'])**2 + (y - vertex['y'])**2)
        if distance < 7:
            draw_edge(vertex, vertices[vertex['id']], edge_status=True)


def break_camera(event=None):
    # todo Тут будет отправка на сервер
    global vertices
    x, y = event.x, event.y
    for vertex in vertices:
        distance = math.sqrt((x - vertex['x'])**2 + (y - vertex['y'])**2)
        if distance < 7:
            print(vertices)
            canvas.delete(vertex['rid'])
            x, y = vertex['x'], vertex['y']
            vindex = vertex['id']
            draw_camera(x=x, y=y, vindex=vindex, cam_status='Bad')
            print(vertices)


if __name__ == '__main__':
    root = tk.Tk()
    root.title('Smart Light Visualizer')
    root.geometry('650x800')
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=1)

    root.bind('<Up>', lambda event: connect_to_server())

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

    status_ = tk.StringVar(value='Подключено')
    st = 'green'
    statusL = ttk.Label(main_frame, textvariable=status_, foreground=st)
    statusL.grid(column=2, row=0)

    canvas = tk.Canvas(height=600, width=800, bg='white')
    canvas.bind('<Button-1>', find_car)
    canvas.bind('<Button-3>', break_camera)
    canvas.grid(column=0, row=1, sticky='nsew', columnspan=3)

    root.mainloop()