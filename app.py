import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import messagebox, filedialog
import sqlite3
import requests
import math
import threading
import time
import os
import zipfile
from cryptography.fernet import Fernet
from PIL import Image, ImageTk
import gdown

def center_window(win, width, height):
    win.update_idletasks()
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")

SECRET_KEY = b'LuNo7QH0oR3w9r3U9ZRCQ67UysCxg61Oa6HavzdSE1E='
fernet = Fernet(SECRET_KEY)

def decrypt_url(encrypted_url: str) -> str:
    try:
        return fernet.decrypt(encrypted_url.encode()).decode()
    except Exception as e:
        messagebox.showerror("Error", f"Error al desencriptar la URL: {e}")
        return ""

def encrypt_url(url: str) -> str:
    try:
        return fernet.encrypt(url.encode()).decode()
    except Exception as e:
        messagebox.showerror("Error", f"Error al encriptar la URL: {e}")
        return ""

def get_theme_from_settings() -> str:
    try:
        conn = sqlite3.connect("data/data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT theme FROM settings LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception as e:
        pass
    return "flatly"

def get_page_size() -> int:
    try:
        conn = sqlite3.connect("data/data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT page FROM settings LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return int(row[0])
    except Exception as e:
        pass
    return 30

current_theme = get_theme_from_settings()

class Application(ttk.Window):
    def __init__(self):
        super().__init__(themename=current_theme)
        self.title("Backup ROMs Free")
        self.geometry("900x605")
        center_window(self, 900, 605)
        self.resizable(True, True)
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "flags/icon.png")
            self.iconphoto(False, tk.PhotoImage(file=icon_path))
        except Exception as e:
            print("No se pudo cargar el icono:", e)

        self.download_path = os.path.join(os.getcwd(), "download")
        print(self.download_path)

        consoles = self.load_consoles()
        regions = self.load_regions()

        self.system = tk.StringVar(value="Todos")
        self.search_term = tk.StringVar()
        self.region = tk.StringVar(value="Todos")
        self.page_size = get_page_size()

        menubar = tk.Menu(self)
        menubar.add_command(label="Configuraciones", command=self.open_settings_window)
        menubar.add_command(label="Actualizar BD", command=self.update_database)
        menubar.add_command(label="Historial de descargas", command=self.open_history_window)
        self.config(menu=menubar)

        top_frame = ttk.Frame(self)
        top_frame.pack(pady=5, padx=10, fill=tk.X)

        ttk.Label(top_frame, text="Consola:").pack(side=tk.LEFT)
        system_menu = ttk.Combobox(top_frame, textvariable=self.system, state="readonly",
                                   values=consoles, width=20)
        system_menu.pack(side=tk.LEFT, padx=5)

        ttk.Label(top_frame, text="Región:").pack(side=tk.LEFT, padx=10)
        region_combo = ttk.Combobox(top_frame, textvariable=self.region, state="readonly",
                                    values=regions, width=15)
        region_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(top_frame, text="Buscar por nombre:").pack(side=tk.LEFT, padx=10)
        search_entry = ttk.Entry(top_frame, textvariable=self.search_term, width=31)
        search_entry.pack(side=tk.LEFT, padx=5)

        search_btn = ttk.Button(top_frame, text="Buscar", command=self.fetch_data)
        search_btn.pack(side=tk.LEFT, padx=5)

        refresh_btn = ttk.Button(top_frame, text="Refrescar", command=self.reset_search)
        refresh_btn.pack(side=tk.LEFT, padx=0)

        self.current_page = 1
        self.all_files = []

        self.region_pil = {}
        self.images = {}
        try:
            desired_size = (25, 15)
            for key, filename in {
                "default":"default.png",
                "japan":"japan.png",
                "usa":"usa.png",
                "europe":"europe.png",
                "france":"france.png",
                "germany":"germany.png",
                "spain":"spain.png",
                "italy":"italy.png",
                "taiwan":"taiwan.png",
                "sweden":"sweden.png",
                "scandinavia":"scandinavia.png",
                "australia":"australia.jpg",
                "Russia":"Russia.png",
                "korea":"korea.png",
                "netherlands":"netherlands.png",
                "uk":"uk.png",
                "portugal":"portugal.png",
                "asia":"default.png",
                "finland":"finland.png",
                "denmark":"denmark.png",
                "norway":"norway.png",
                "greece":"greece.png",
                "israel":"israel.png",
                "china":"china.png",
                "poland":"poland.png",
                "canada":"canada.png",
                "belgium":"belgium.jpg",
                "ireland":"ireland.png",
                "austria":"austria.jpg",
                "japan, asia":"default.png",
                "europe, australia":"default.png",
                "belgium, netherlands":"default.png",
                "usa, europe":"default.png",
                "usa, canada":"default.png",
                "austria, switzerland":"default.png",
                "switzerland":"switzerland.png",
                "india":"india.png",
                "japan, korea":"default.png",
                "uk, australia":"default.png",
                "latin america":"default.png",
                "brazil":"brazil.png",
                "usa, brazil":"default.png",
                "france, spain":"default.png",
                "spain, portugal":"default.png",
                "south africa":"new-zealand.png",
                "croatia":"croatia.png",
                "World":"default.png",
                "usa, asia":"default.png",
                "europe, asia":"default.png",
                "usa, korea":"default.png",
                "united arab emirates":"united-arab-emirates.png",
                "turkey":"turkey.png",
                "japan, europe":"default.png",
                "usa, japan":"default.png",
                "new Zealand":"new-zealand.png",
                "australia, new Zealand":"default.png",
                "europe, canada":"default.png",
                "usa, australia":"default.png"
            }.items():
                pil_img = Image.open(os.path.join("flags", filename)).resize(desired_size, Image.Resampling.LANCZOS)
                self.region_pil[key] = pil_img
                self.images[key] = ImageTk.PhotoImage(pil_img)
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar las imágenes de región: {e}")

        self.composite_images = {}

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        columns = ("Servidor", "Type", "Name", "Size", "Download")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings")
        self.tree.heading("#0", text="Región")
        self.tree.heading("Servidor", text="Servidor")
        self.tree.heading("Type", text="Consola")
        self.tree.heading("Name", text="Nombre")
        self.tree.heading("Size", text="Tamaño")
        self.tree.heading("Download", text="Descargar")
        self.tree.column("#0", width=60)
        self.tree.column("Servidor", width=60)
        self.tree.column("Type", width=70)
        self.tree.column("Name", width=350)
        self.tree.column("Size", width=100)
        self.tree.column("Download", width=50)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)

        pagination_frame = ttk.Frame(self)
        pagination_frame.pack(pady=5)
        self.prev_btn = ttk.Button(pagination_frame, text="Anterior", command=self.prev_page)
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        self.page_info_label = ttk.Label(pagination_frame, text="Página 0 de 0")
        self.page_info_label.pack(side=tk.LEFT, padx=5)
        self.next_btn = ttk.Button(pagination_frame, text="Siguiente", command=self.next_page)
        self.next_btn.pack(side=tk.LEFT, padx=5)

        self.item_url_mapping = {}

        self.fetch_data()

    def load_consoles(self):
        try:
            conn = sqlite3.connect("data/data.db")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM console ORDER BY name ASC")
            rows = cursor.fetchall()
            conn.close()
            consoles = [row[0] for row in rows]
            if "Todos" not in consoles:
                consoles.insert(0, "Todos")
            return consoles
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar consolas: {e}")
            return ["Todos"]

    def load_regions(self):
        try:
            conn = sqlite3.connect("data/data.db")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM region ORDER BY name ASC")
            rows = cursor.fetchall()
            conn.close()
            regions = [row[0] for row in rows]
            if "Todos" not in regions:
                regions.insert(0, "Todos")
            return regions if regions else ["Todos"]
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar regiones: {e}")
            return ["Todos"]

    def reset_search(self):
        self.search_term.set("")
        self.fetch_data()

    def set_download_path(self):
        path = filedialog.askdirectory(title="Selecciona la carpeta de descarga")
        if path:
            self.download_path = path
            messagebox.showinfo("Configuraciones", f"Ruta de descarga establecida: {self.download_path}")

    def open_settings_window(self):
        settings_win = tk.Toplevel(self)
        settings_win.title("Configuraciones")
        settings_win.geometry("400x350")
        center_window(settings_win, 400, 350)
        settings_win.resizable(False, False)
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "flags/icon.png")
            settings_win.iconphoto(False, tk.PhotoImage(file=icon_path))
        except Exception as e:
            pass

        unzip_var = tk.BooleanVar()
        decryp_var = tk.BooleanVar()
        path_var = tk.StringVar()
        theme_var = tk.StringVar()
        theme_options = ["flatly", "litera", "darkly", "journal", "cyborg", "superhero", "minty", "pulse", "simplex", "vapor"]
        page_var = tk.StringVar()

        settings = self.load_settings()
        if settings is None:
            settings = {"unzip": "N", "path": os.path.join(os.getcwd(), "download"), "decryp": "N", "theme": "flatly", "page": 30}
        unzip_var.set(True if settings["unzip"].upper() == "S" else False)
        path_var.set(settings["path"])
        decryp_var.set(True if settings["decryp"].upper() == "S" else False)
        theme_var.set(settings.get("theme", "flatly"))
        page_var.set(str(settings["page"]))

        ttk.Label(settings_win, text="Descomprimir al finalizar la descarga:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Checkbutton(settings_win, variable=unzip_var).pack(anchor=tk.W, padx=20)

        ttk.Label(settings_win, text="Ruta de descarga:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Entry(settings_win, textvariable=path_var, width=70).pack(anchor=tk.W, padx=20)

        ttk.Label(settings_win, text="Encriptar:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Checkbutton(settings_win, variable=decryp_var).pack(anchor=tk.W, padx=20)

        ttk.Label(settings_win, text="Tema:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Combobox(settings_win, textvariable=theme_var, values=theme_options, state="readonly", width=68).pack(anchor=tk.W, padx=20)

        def validate_page(P):
            if P == "":
                return True
            try:
                num = int(P)
                return 1 <= num <= 100
            except:
                return False
        vcmd = (settings_win.register(validate_page), '%P')
        ttk.Label(settings_win, text="Paginación:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Entry(settings_win, textvariable=page_var, width=70, validate="key", validatecommand=vcmd).pack(anchor=tk.W, padx=20)

        button_frame = ttk.Frame(settings_win)
        button_frame.pack(pady=30)
        ttk.Button(button_frame, text="Guardar", command=lambda: (
            self.update_settings("S" if unzip_var.get() else "N",
                                 path_var.get().strip() if path_var.get().strip() != "" else os.path.join(os.getcwd(), "download"),
                                 "S" if decryp_var.get() else "N",
                                 theme_var.get(),
                                 int(page_var.get()) if page_var.get().isdigit() else 30),
            settings_win.destroy()
        )).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancelar", command=settings_win.destroy).pack(side=tk.LEFT, padx=10)

    def load_settings(self):
        try:
            conn = sqlite3.connect("data/data.db")
            cursor = conn.cursor()
            cursor.execute("SELECT unzip, path, decryp, theme, page FROM settings LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row:
                return {"unzip": row[0], "path": row[1], "decryp": row[2], "theme": row[3], "page": row[4]}
            else:
                return None
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar la configuración: {e}")
            return None

    def update_settings(self, unzip, path, decryp, theme, page):
        try:
            conn = sqlite3.connect("data/data.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM settings")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute("INSERT INTO settings (unzip, path, decryp, theme, page) VALUES (?, ?, ?, ?, ?)", (unzip, path, decryp, theme, page))
            else:
                cursor.execute("UPDATE settings SET unzip=?, path=?, decryp=?, theme=?, page=?", (unzip, path, decryp, theme, page))
            conn.commit()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar la configuración: {e}")

    def update_database(self):
        db_url = "https://github.com/3rikdani3l/BackupROMsFree/raw/refs/heads/main/data/data.db"
        data_folder = os.path.join(os.getcwd(), "data")
        os.makedirs(data_folder, exist_ok=True)
        destination = os.path.join(data_folder, "data.db")

        download_win = tk.Toplevel(self)
        download_win.title("Actualizando Base de Datos")
        download_win.geometry("400x200")
        center_window(download_win, 400, 200)
        download_win.resizable(False, False)
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "flags/icon.png")
            download_win.iconphoto(False, tk.PhotoImage(file=icon_path))
        except Exception as e:
            pass

        label_file = ttk.Label(download_win, text="Descargando Base de Datos")
        label_file.pack(pady=5)

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(download_win, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=20, pady=10)

        label_speed = ttk.Label(download_win, text="Velocidad: 0 KB/s")
        label_speed.pack(pady=5)

        label_eta = ttk.Label(download_win, text="Tiempo restante: 0 s")
        label_eta.pack(pady=5)

        def update_progress(downloaded, total, speed, remaining):
            percent = (downloaded / total) * 100 if total else 0
            progress_var.set(percent)
            label_speed.config(text=f"Velocidad: {speed/1024:.2f} KB/s")
            label_eta.config(text=f"Tiempo restante: {int(remaining)} s")

        def finish_download(success, info):
            if success:
                messagebox.showinfo("BD Actualizada", f"Base de datos actualizada en:\n{info}")
            else:
                messagebox.showerror("Error en actualización", f"Ocurrió un error:\n{info}")
            download_win.destroy()

        def perform_download():
            try:
                response = requests.get(db_url, stream=True)
                total = int(response.headers.get("content-length", 0))
                downloaded = 0
                start_time = time.time()
                chunk_size = 8192
                with open(destination, "wb") as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            elapsed = time.time() - start_time
                            speed = downloaded / elapsed if elapsed > 0 else 0
                            remaining = (total - downloaded) / speed if speed > 0 else 0
                            download_win.after(0, update_progress, downloaded, total, speed, remaining)
                download_win.after(0, finish_download, True, destination)
            except Exception as e:
                download_win.after(0, finish_download, False, str(e))

        threading.Thread(target=perform_download, daemon=True).start()

    def fetch_data(self):
        system = self.system.get().lower()
        query = self.search_term.get().strip().lower()
        region_filter = self.region.get().lower()

        try:
            conn = sqlite3.connect("data/data.db")
            cursor = conn.cursor()
            sql = "SELECT name, region, size, type, url, encrypted, server FROM files WHERE 1=1"
            params = []
            if system != "todos":
                sql += " AND lower(type)=?"
                params.append(system)
            if query:
                sql += " AND lower(name) LIKE ?"
                params.append(f"%{query}%")
            if region_filter != "todos":
                sql += " AND lower(region)=?"
                params.append(region_filter)
            sql += " ORDER BY name ASC"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()
            self.all_files = rows
            self.current_page = 1
            self.display_page()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los datos: {e}")

    def create_composite_image(self, region_value, server_value):
        region_key = region_value.lower()
        if region_key not in self.region_pil:
            region_key = "default"
        return self.images[region_key]

    def display_page(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        total_items = len(self.all_files)
        total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        if self.current_page < 1:
            self.current_page = 1
        elif self.current_page > total_pages:
            self.current_page = total_pages

        start_index = (self.current_page - 1) * self.page_size
        end_index = start_index + self.page_size

        self.item_url_mapping = {}
        self.composite_images.clear()
        for file in self.all_files[start_index:end_index]:
            name, region_value, size, _type, url, encrypted, server_value = file
            comp_img = self.create_composite_image(region_value, server_value)
            key = f"{name}_{server_value}"
            self.composite_images[key] = comp_img
            item_id = self.tree.insert("", tk.END, text="", image=comp_img,
                                       values=(server_value, _type, name, size, "Download"))
            self.item_url_mapping[item_id] = {"url": url, "name": name, "encrypted": encrypted, "server": server_value}

        self.page_info_label.config(text=f"Página {self.current_page} de {total_pages}")
        self.prev_btn.config(state=tk.DISABLED if self.current_page <= 1 else tk.NORMAL)
        self.next_btn.config(state=tk.DISABLED if self.current_page >= total_pages else tk.NORMAL)

    def on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if item_id and column == "#5":
            info = self.item_url_mapping.get(item_id)
            if info:
                if info["encrypted"].upper() == "S":
                    real_url = decrypt_url(info["url"])
                else:
                    real_url = info["url"]
                file_name = info["name"]
                server_name = info["server"]
                self.start_download(real_url, file_name, server_name)

    def start_download(self, url, file_name, server_name):
        if server_name.upper() == "GOOGLE DRIVE":
            file_path = os.path.join(self.download_path, file_name)
            output = file_path
            id = url
            try:
                head_url = "https://drive.google.com/uc?export=download&id=" + id
                head_response = requests.head(head_url)
                total = int(head_response.headers.get("content-length", 0))
            except Exception as e:
                total = 0

            download_win = tk.Toplevel(self)
            download_win.title(f"Descargando: {file_name}")
            download_win.geometry("400x220")
            center_window(download_win, 400, 220)
            download_win.resizable(False, False)
            try:
                icon_path = os.path.join(os.path.dirname(__file__), "flags/icon.png")
                download_win.iconphoto(False, tk.PhotoImage(file=icon_path))
            except Exception as e:
                pass

            label_file = ttk.Label(download_win, text=f"Archivo: {file_name}")
            label_file.pack(pady=5)

            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(download_win, variable=progress_var, maximum=100)
            progress_bar.pack(fill=tk.X, padx=20, pady=10)

            label_sizes = ttk.Label(download_win, text="Total: 0 B | Descargado: 0 B | Faltante: 0 B")
            label_sizes.pack(pady=5)

            label_speed = ttk.Label(download_win, text="Velocidad: 0 KB/s")
            label_speed.pack(pady=5)

            label_eta = ttk.Label(download_win, text="Tiempo restante: 0 s")
            label_eta.pack(pady=5)

            cancel_btn = ttk.Button(download_win, text="Cancelar")
            cancel_btn.pack(pady=5)
            cancel_flag = [False]
            def cancel_download():
                cancel_flag[0] = True
                messagebox.showinfo("Descarga cancelada", "La descarga ha sido cancelada.")
                download_win.destroy()
            cancel_btn.config(command=cancel_download)

            def format_size(b):
                if b < 1024:
                    return f"{b} B"
                elif b < 1024*1024:
                    return f"{b/1024:.2f} KB"
                elif b < 1024*1024*1024:
                    return f"{b/(1024*1024):.2f} MB"
                else:
                    return f"{b/(1024*1024*1024):.2f} GB"

            def format_time(seconds):
                seconds = int(seconds)
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                secs = seconds % 60
                if hours > 0:
                    return f"{hours}h {minutes}m {secs}s"
                elif minutes > 0:
                    return f"{minutes}m {secs}s"
                else:
                    return f"{secs}s"

            def update_progress(downloaded, total, speed, remaining):
                percent = (downloaded / total) * 100 if total else 0
                progress_var.set(percent)
                label_sizes.config(text=f"Total: {format_size(total)} | Descargado: {format_size(downloaded)} | Faltante: {format_size(total - downloaded)}")
                label_speed.config(text=f"Velocidad: {speed/1024:.2f} KB/s")
                label_eta.config(text=f"Tiempo restante: {format_time(remaining)}")

            def finish_download(success, info):
                if success:
                    current_settings = self.load_settings()
                    if (file_name.lower().endswith('.zip') or file_name.lower().endswith('.rar')) and current_settings and current_settings["unzip"].upper() == "S":
                        extract_path = os.path.join(self.download_path, os.path.splitext(file_name)[0])
                        try:
                            if file_name.lower().endswith('.zip'):
                                with zipfile.ZipFile(info, 'r') as zip_ref:
                                    zip_ref.extractall(extract_path)
                            elif file_name.lower().endswith('.rar'):
                                import rarfile
                                with rarfile.RarFile(info, 'r') as rar_ref:
                                    rar_ref.extractall(extract_path)
                            messagebox.showinfo("Descarga completada", f"Archivo guardado en:\n{info}\nDescomprimido en:\n{extract_path}")
                        except Exception as e:
                            messagebox.showerror("Error al descomprimir", f"Error al descomprimir el archivo: {e}")
                    else:
                        if server_name != "Google Drive":
                            messagebox.showinfo("Descarga completada", f"Archivo guardado en:\n{info}")
                    try:
                        conn = sqlite3.connect("data/data.db")
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO history (name) VALUES (?)", (file_name,))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        messagebox.showerror("Error", f"Error al insertar en history: {e}")
                else:
                    messagebox.showerror("Error en descargar", f"El archivo " + file_name + " no tiene permiso como publico para ser descargado desde Google Drive.")
                download_win.destroy()

            def perform_gdrive_download():
                try:
                    gdown.download(id=id, output=output, quiet=True)
                except Exception as e:
                    download_win.after(0, finish_download, False, str(e))
                if not cancel_flag[0]:
                    download_win.after(0, finish_download, True, file_path)

            def poll_progress():
                start_time = time.time()
                while not cancel_flag[0]:
                    if os.path.exists(file_path):
                        downloaded = os.path.getsize(file_path)
                    else:
                        downloaded = 0
                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    remaining = (total - downloaded) / speed if speed > 0 else 0
                    download_win.after(0, update_progress, downloaded, total, speed, remaining)
                    if total != 0 and downloaded >= total:
                        break
                    time.sleep(0.5)

            threading.Thread(target=perform_gdrive_download, daemon=True).start()
            threading.Thread(target=poll_progress, daemon=True).start()
            return
        
        if server_name.upper() == "NOPAYSTATION":
            file_name = file_name + ".pkg"

        download_win = tk.Toplevel(self)
        download_win.title(f"Descargando: {file_name}")
        download_win.geometry("400x220")
        center_window(download_win, 400, 220)
        download_win.resizable(False, False)
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "flags/icon.png")
            download_win.iconphoto(False, tk.PhotoImage(file=icon_path))
        except Exception as e:
            pass

        label_file = ttk.Label(download_win, text=f"Archivo: {file_name}")
        label_file.pack(pady=5)

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(download_win, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=20, pady=10)

        label_sizes = ttk.Label(download_win, text="Total: 0 B | Descargado: 0 B | Faltante: 0 B")
        label_sizes.pack(pady=5)

        label_speed = ttk.Label(download_win, text="Velocidad: 0 KB/s")
        label_speed.pack(pady=5)

        label_eta = ttk.Label(download_win, text="Tiempo restante: 0 s")
        label_eta.pack(pady=5)

        cancel_btn = ttk.Button(download_win, text="Cancelar")
        cancel_btn.pack(pady=5)
        cancel_flag = [False]
        def cancel_download():
            cancel_flag[0] = True
            messagebox.showinfo("Descarga cancelada", "La descarga ha sido cancelada.")
            download_win.destroy()
        cancel_btn.config(command=cancel_download)

        file_path = os.path.join(self.download_path, file_name)
        
        def format_size(b):
            if b < 1024:
                return f"{b} B"
            elif b < 1024*1024:
                return f"{b/1024:.2f} KB"
            elif b < 1024*1024*1024:
                return f"{b/(1024*1024):.2f} MB"
            else:
                return f"{b/(1024*1024*1024):.2f} GB"

        def format_time(seconds):
            seconds = int(seconds)
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            if hours > 0:
                return f"{hours}h {minutes}m {secs}s"
            elif minutes > 0:
                return f"{minutes}m {secs}s"
            else:
                return f"{secs}s"

        def update_progress(downloaded, total, speed, remaining):
            percent = (downloaded / total) * 100 if total else 0
            progress_var.set(percent)
            label_sizes.config(text=f"Total: {format_size(total)} | Descargado: {format_size(downloaded)} | Faltante: {format_size(total - downloaded)}")
            label_speed.config(text=f"Velocidad: {speed/1024:.2f} KB/s")
            label_eta.config(text=f"Tiempo restante: {format_time(remaining)}")

        def finish_download(success, info):
            if success:
                current_settings = self.load_settings()
                if (file_name.lower().endswith('.zip') or file_name.lower().endswith('.rar')) and current_settings and current_settings["unzip"].upper() == "S":
                    extract_path = os.path.join(self.download_path, os.path.splitext(file_name)[0])
                    try:
                        if file_name.lower().endswith('.zip'):
                            with zipfile.ZipFile(info, 'r') as zip_ref:
                                zip_ref.extractall(extract_path)
                        elif file_name.lower().endswith('.rar'):
                            import rarfile
                            with rarfile.RarFile(info, 'r') as rar_ref:
                                rar_ref.extractall(extract_path)
                        messagebox.showinfo("Descarga completada", f"Archivo guardado en:\n{info}\nDescomprimido en:\n{extract_path}")
                    except Exception as e:
                        messagebox.showerror("Error al descomprimir", f"Error al descomprimir el archivo: {e}")
                else:
                    messagebox.showinfo("Descarga completada", f"Archivo guardado en:\n{info}")
                try:
                    conn = sqlite3.connect("data/data.db")
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO history (name) VALUES (?)", (file_name,))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    messagebox.showerror("Error", f"Error al insertar en history: {e}")
            download_win.destroy()

        def perform_download():
            try:
                response = requests.get(url, stream=True)
                total = int(response.headers.get("content-length", 0))
                downloaded = 0
                start_time = time.time()
                chunk_size = 8192
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if cancel_flag[0]:
                            f.close()
                            os.remove(file_path)
                            download_win.after(0, finish_download, False, "Descarga cancelada")
                            return
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            elapsed = time.time() - start_time
                            speed = downloaded / elapsed if elapsed > 0 else 0
                            remaining = (total - downloaded) / speed if speed > 0 else 0
                            download_win.after(0, update_progress, downloaded, total, speed, remaining)
                download_win.after(0, finish_download, True, file_path)
            except Exception as e:
                download_win.after(0, finish_download, False, str(e))

        threading.Thread(target=perform_download, daemon=True).start()

    def next_page(self):
        total_items = len(self.all_files)
        total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        if self.current_page < total_pages:
            self.current_page += 1
            self.display_page()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.display_page()

    def open_history_window(self):
        history_win = tk.Toplevel(self)
        history_win.title("Historial de descargas")
        history_win.geometry("500x400")
        center_window(history_win, 500, 400)
        history_win.resizable(False, False)
        
        columns = ("Archivo", "Estado")
        history_tree = ttk.Treeview(history_win, columns=columns, show="headings")
        history_tree.heading("Archivo", text="Archivo")
        history_tree.heading("Estado", text="Estado")
        history_tree.column("Archivo", width=350)
        history_tree.column("Estado", width=100)
        history_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        try:
            conn = sqlite3.connect("data/data.db")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM history ORDER BY id DESC")
            rows = cursor.fetchall()
            conn.close()
            for row in rows:
                file_name = row[0]
                file_path = os.path.join(self.download_path, file_name)
                if os.path.exists(file_path):
                    history_tree.insert("", tk.END, values=(file_name, "Disponible"))
                else:
                    history_tree.insert("", tk.END, values=(file_name, "No disponible"))

            icon_path = os.path.join(os.path.dirname(__file__), "flags/icon.png")
            history_win.iconphoto(False, tk.PhotoImage(file=icon_path))
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar el historial: {e}")

        def on_history_click(event):
            item = history_tree.selection()
            if item:
                archivo = history_tree.item(item, "values")[0]
                file_path = os.path.join(self.download_path, archivo)
                if os.path.exists(file_path):
                    try:
                        os.startfile(file_path)
                    except Exception as e:
                        messagebox.showerror("Error", f"No se pudo abrir el archivo: {e}")

        history_tree.bind("<Double-1>", on_history_click)
        
        def clear_history():
            try:
                conn = sqlite3.connect("data/data.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM history")
                conn.commit()
                conn.close()
                for item in history_tree.get_children():
                    history_tree.delete(item)
            except Exception as e:
                messagebox.showerror("Error", f"Error al borrar historial: {e}")
        
        btn_clear_history = ttk.Button(history_win, text="Borrar Historial", command=clear_history)
        btn_clear_history.pack(pady=10)

    def open_crud_window(self):
        crud_win = tk.Toplevel(self)
        crud_win.title("Actualizar BD - Insertar Registro")
        crud_win.geometry("300x350")
        center_window(crud_win, 300, 350)
        crud_win.resizable(False, False)
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "flags/icon.png")
            crud_win.iconphoto(False, tk.PhotoImage(file=icon_path))
        except Exception as e:
            pass

        ttk.Label(crud_win, text="Nombre de la rom:").pack(anchor=tk.W, padx=10, pady=5)
        name_entry = ttk.Entry(crud_win, width=50)
        name_entry.pack(anchor=tk.W, padx=20)

        ttk.Label(crud_win, text="Región:").pack(anchor=tk.W, padx=10, pady=5)
        regions = self.load_regions()
        if "Unknow" not in regions:
            regions.insert(0, "Unknow")
        region_var = tk.StringVar(value="Unknow")
        region_combo = ttk.Combobox(crud_win, textvariable=region_var, values=regions, state="readonly", width=47)
        region_combo.pack(anchor=tk.W, padx=20)

        weight_frame = ttk.Frame(crud_win)
        weight_frame.pack(anchor=tk.W, padx=20, pady=5)
        ttk.Label(weight_frame, text="Peso:").pack(side=tk.LEFT)
        weight_entry = ttk.Entry(weight_frame, width=20)
        weight_entry.pack(side=tk.LEFT, padx=5)
        unit_var = tk.StringVar(value="MiB")
        unit_combo = ttk.Combobox(weight_frame, textvariable=unit_var, values=["MiB", "GiB"], state="readonly", width=10)
        unit_combo.pack(side=tk.LEFT)

        ttk.Label(crud_win, text="Consola:").pack(anchor=tk.W, padx=10, pady=5)
        consoles = self.load_consoles()
        default_console = consoles[0] if consoles else ""
        console_var = tk.StringVar(value=default_console)
        console_combo = ttk.Combobox(crud_win, textvariable=console_var, values=consoles, state="readonly", width=47)
        console_combo.pack(anchor=tk.W, padx=20)

        ttk.Label(crud_win, text="URL:").pack(anchor=tk.W, padx=10, pady=5)
        url_entry = ttk.Entry(crud_win, width=50)
        url_entry.pack(anchor=tk.W, padx=20)

        def insert_record():
            name = name_entry.get().strip()
            region = region_var.get().strip()
            weight = weight_entry.get().strip()
            unit = unit_var.get().strip()
            console = console_var.get().strip()
            url = url_entry.get().strip()

            if not name:
                messagebox.showerror("Error", "El campo Nombre es obligatorio.")
                return
            if not url:
                messagebox.showerror("Error", "El campo URL es obligatorio.")
                return
            size = f"{weight} {unit}" if weight else ""
            settings = self.load_settings()
            if settings and settings["decryp"].upper() == "S":
                encrypted_url = encrypt_url(url)
            else:
                encrypted_url = url
            server = "Otros"
            try:
                conn = sqlite3.connect("data/data.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO files (name, region, size, type, url, encrypted, server) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (name, region, size, console, encrypted_url, settings["decryp"] if settings else "N", server))
                conn.commit()
                conn.close()
                messagebox.showinfo("BD", "Registro insertado correctamente.")
                crud_win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Error al insertar el registro: {e}")

        ttk.Button(crud_win, text="Guardar", command=insert_record).pack(pady=20)

    def next_page(self):
        total_items = len(self.all_files)
        total_pages = math.ceil(total_items / self.page_size) if total_items > 0 else 1
        if self.current_page < total_pages:
            self.current_page += 1
            self.display_page()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.display_page()

if __name__ == "__main__":
    app = Application()
    app.mainloop()
