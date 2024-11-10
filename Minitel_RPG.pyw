import subprocess, threading, time
from datetime import datetime

try:
    import serial
except ImportError:
    subprocess.check_call(["python", "-m", "pip", "install", "pyserial"])
    import serial
import serial.tools.list_ports

try:
    import tkinter as tk
except ImportError:
    subprocess.check_call(["python", "-m", "pip", "install", "tkinter"])
    import tkinter as tk
from tkinter import ttk, messagebox

import xml.etree.ElementTree as ET

version = 0.1

TILE_WIDTH, TILE_HEIGHT = 8, 9
X_STEP, Y_STEP = TILE_WIDTH // 2, TILE_HEIGHT // 3
SCREEN_TILES_HEIGHT, SCREEN_TILES_WIDTH = 8, 10  # Dimensions de l'écran en tuiles (8x10)

DEFAULT_MINITEL_MODEL = "Minitel 1B and later"
connection_active, ser = False, None

key_direction_map = {
    'Q': 0,
    'D': 1,
    'S': 2,
    'Z': 3
}

from image_to_G1_converter import *

player_x, player_y = 1, 1

sprite_player = image_to_G1("player.bmp")
tiles = image_to_G1("tiles.bmp")

def load_tmx_map_csv(filename):
    tree = ET.parse(filename)
    root = tree.getroot()
    width = int(root.attrib['width'])
    height = int(root.attrib['height'])
    layer = root.find('layer')
    data = layer.find('data').text.strip()
    tile_ids = [int(tile_id) for tile_id in data.split(',')]
    tile_map = [tile_ids[i:i + width] for i in range(0, len(tile_ids), width)]
    return tile_map

current_map = load_tmx_map_csv("map1.tmx")

def open_gui():
    window = tk.Tk()
    window.title("Minitel RS232/USB - Jeu")
    window.geometry("400x600")
    window.columnconfigure(0, weight=1)
    window.columnconfigure(1, weight=3)
    window.rowconfigure(8, weight=1)

    model_var, com_port_var = tk.StringVar(value=DEFAULT_MINITEL_MODEL), tk.StringVar()
    baudrate_var, data_bits_var = tk.IntVar(), tk.IntVar()
    parity_var, stop_bits_var = tk.StringVar(), tk.IntVar(value=1)
    show_messages_var, encoding_var = tk.BooleanVar(value=True), tk.StringVar(value="hexadecimal")

    def clear_console():
        console.config(state='normal')
        console.delete('1.0', tk.END)
        console.config(state='disabled')

    def log_message(message, is_communication=False):
        if is_communication and not show_messages_var.get():
            return
        console.config(state='normal')
        console.insert(tk.END, f"{datetime.now().strftime('[%H:%M:%S] ')}{message}\n")
        console.config(state='disabled')
        console.see(tk.END)

    def list_serial_ports():
        ports = serial.tools.list_ports.comports()
        return [f"{port.device} - {port.description}" for port in ports]

    def apply_model_settings(*args):
        clear_console()
        model = model_var.get()
        if model == "Minitel 1":
            baudrate_menu['values'] = [1200]
            baudrate_var.set(1200)
            data_bits_var.set(7)
            parity_var.set("Even")
        elif model == "Minitel 1B and later":
            baudrate_menu['values'] = [300, 1200, 4800]
            baudrate_var.set(4800)
            data_bits_var.set(7)
            parity_var.set("Even")
            log_message("To configure the serial port speed on your Minitel:")
            log_message("Fcnt + P, 3: 300 bits/s")
            log_message("Fcnt + P, 1: 1200 bits/s")
            log_message("Fcnt + P, 4: 4800 bits/s")
        elif model == "Minitel 2 or Magis Club":
            baudrate_menu['values'] = [300, 1200, 4800, 9600]
            baudrate_var.set(9600)
            data_bits_var.set(8 if baudrate_var.get() == 9600 else 7)
            parity_var.set("None" if baudrate_var.get() == 9600 else "Even")
            log_message("To configure the serial port speed on your Minitel:")
            log_message("Fcnt + P, 3: 300 bits/s")
            log_message("Fcnt + P, 1: 1200 bits/s")
            log_message("Fcnt + P, 4: 4800 bits/s")
            log_message("Fcnt + P, 9: 9600 bits/s")

    def get_tile_data(x, y, tile_index):
        tile = tiles[tile_index-1]
        data = b""
        for tile_row, tile_line in enumerate(tile):
            screen_y = y * Y_STEP + tile_row# + 1
            screen_x = x * X_STEP + 1
            tile_bytes = b''.join(bytes.fromhex(value) for value in tile_line)
            data += f"\x1B[{screen_y};{screen_x}H".encode('utf-8') + tile_bytes
        return data

    def render_map():
        if ser and ser.is_open:
            ser.write(b'\x0C')
            ser.write(b'\x0E')
            data = b""
            for row in range(SCREEN_TILES_HEIGHT):
                for col in range(SCREEN_TILES_WIDTH):
                    if row < len(current_map) and col < len(current_map[0]) and current_map[row][col]-1 != 0:
                        data += get_tile_data(col, row, current_map[row][col])
            ser.write(data)

    def draw_player(x, y, direction_index):
        if ser and ser.is_open:
            sprite = sprite_player[direction_index]
            color_code = sprite[0][0]
            ser.write(bytes.fromhex(color_code))
            data = b""
            for row_idx, row in enumerate(sprite[1:]):
                for col_idx, hex_code in enumerate(row):
                    data += f"\x1B[{y * Y_STEP + row_idx + 1};{x * X_STEP + col_idx + 1}H".encode('utf-8')
                    data += bytes.fromhex(hex_code)
            ser.write(data)

    def handle_keys():
        global player_x, player_y
        while True:
            if ser and ser.is_open:
                key_data = ser.read(1)
                if key_data:
                    key = key_data.decode('utf-8', errors='ignore').upper()
                    if key == 'Z' and player_y > 0:
                        ser.write(get_tile_data(player_x, player_y, current_map[player_y][player_x]))
                        player_y -= 1
                        draw_player(player_x, player_y, key_direction_map.get(key))
                    elif key == 'S' and player_y < SCREEN_TILES_HEIGHT-1:
                        ser.write(get_tile_data(player_x, player_y, current_map[player_y][player_x]))
                        player_y += 1
                        draw_player(player_x, player_y, key_direction_map.get(key))
                    elif key == 'Q' and player_x > 0:
                        ser.write(get_tile_data(player_x, player_y, current_map[player_y][player_x]))
                        player_x -= 1
                        draw_player(player_x, player_y, key_direction_map.get(key))
                    elif key == 'D' and player_x < SCREEN_TILES_WIDTH-1:
                        ser.write(get_tile_data(player_x, player_y, current_map[player_y][player_x]))
                        player_x += 1
                        draw_player(player_x, player_y, key_direction_map.get(key))
            time.sleep(0.1)

    def start_connection():
        global ser, connection_active
        if connection_active:
            stop_connection()
            return
        selected_com = com_port_var.get().split(" - ")[0]
        if not selected_com:
            log_message("Error: No COM port selected.")
            return
        log_message(f"Starting connection on {selected_com}")
        try:
            ser = serial.Serial(
                port=selected_com, baudrate=baudrate_var.get(),
                bytesize=serial.SEVENBITS if data_bits_var.get() == 7 else serial.EIGHTBITS,
                parity=serial.PARITY_EVEN if parity_var.get().lower() == "even" else serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE if stop_bits_var.get() == 1 else serial.STOPBITS_TWO,
                timeout=1
            )
            connection_active = True
            ser.write(b'\x1B\x3B\x60\x58\x52')  # Désactive l'écho local
            ser.write(b'\x14')  # Masquer le curseur
            ser.write(b'\x0C')  # Efface l'écran
            ser.write(b'\x0E')  # Sélection du jeu de caractères G1

            render_map()

            threading.Thread(target=handle_keys, daemon=True).start()
            log_message("Serial connection established.")
        except serial.SerialException as e:
            log_message(f"Serial connection error: {e}")
            set_connection_state(False)

    def stop_connection():
        if ser and ser.is_open:
            ser.close()
        set_connection_state(False)
        log_message("Connection stopped.")

    def set_connection_state(connected):
        global connection_active
        connection_active = connected
        start_button.config(text="Stop connection" if connected else "Start connection")

    console = tk.Text(window, height=10, state='disabled', wrap='word')
    console.grid(row=8, column=0, columnspan=2, padx=5, pady=5, sticky='nsew')
    console_scrollbar = tk.Scrollbar(window, command=console.yview)
    console_scrollbar.grid(row=8, column=2, sticky='ns')
    console['yscrollcommand'] = console_scrollbar.set

    tk.Label(window, text="Minitel Model:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    model_menu = ttk.Combobox(window, textvariable=model_var, values=["Minitel 1", "Minitel 1B and later", "Minitel 2 or Magis Club"], state='readonly')
    model_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    model_menu.bind("<<ComboboxSelected>>", apply_model_settings)
    tk.Label(window, text="COM Port:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    com_port_menu = ttk.Combobox(window, textvariable=com_port_var, values=list_serial_ports(), state='readonly')
    com_port_menu.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(window, text="Baud Rate:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    baudrate_menu = ttk.Combobox(window, textvariable=baudrate_var, state='readonly')
    baudrate_menu.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(window, text="Data Bits:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    data_bits_menu = ttk.Combobox(window, textvariable=data_bits_var, values=[7, 8], state='readonly')
    data_bits_menu.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(window, text="Parity:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
    parity_menu = ttk.Combobox(window, textvariable=parity_var, values=["None", "Even"], state='readonly')
    parity_menu.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(window, text="Stop Bits:").grid(row=5, column=0, sticky="w", padx=5, pady=5)
    stop_bits_menu = ttk.Combobox(window, textvariable=stop_bits_var, values=[1], state='readonly')
    stop_bits_menu.grid(row=5, column=1, sticky="ew", padx=5, pady=5)
    show_messages_checkbox = tk.Checkbutton(window, text="Show Minitel Communication", variable=show_messages_var)
    show_messages_checkbox.grid(row=9, column=0, columnspan=2, sticky="w", padx=5, pady=5)
    tk.Label(window, text="Encoding:").grid(row=10, column=0, sticky="w", padx=5, pady=5)
    encoding_menu = ttk.Combobox(window, textvariable=encoding_var, values=["hexadecimal", "iso-8859-1", "cp850", "cp437", "iso-8859-15"], state='readonly')
    encoding_menu.grid(row=10, column=1, sticky="ew", padx=5, pady=5)
    start_button = tk.Button(window, text="Start connection", command=start_connection)
    start_button.grid(row=11, column=0, columnspan=2, sticky="ew", padx=5, pady=20)

    apply_model_settings()

    log_message(f"Minitel RS232/USB Telnet Interface v{version}")
    log_message("---")
    log_message("To switch modes on your Minitel :")
    log_message("Fnct + T, V = Teletel videotex CEPT profile 2 25×40")
    log_message("Fnct + T, A = Telematic ISO 6429 American ASCII 25×80 characters")
    log_message("Fnct + T, F = Telematic ISO 6429 French ASCII 25×80 characters")
    log_message("")
    log_message("In Telematic mode :")
    log_message("Fnct + T, E = reverse local echo rule")
    log_message("Ctrl + J = line feed")
    log_message("Ctrl + H = backspace")
    log_message("Ctrl + I = horizontal tabulation")
    log_message("Ctrl + K = vertical tabulation")
    log_message("Ctrl + ← = erase character")
    log_message("Ctrl + X = erase line")
    log_message("↲ = carriage return")
    log_message("")
    log_message("Please consult the Minitel user manual for more information.")
    log_message("---")

    window.mainloop()

open_gui()
