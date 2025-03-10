import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
import requests
import webbrowser
import math
import threading
import time
import os
import json
import zipfile  # Para descomprimir archivos ZIP
from cryptography.fernet import Fernet
from PIL import Image, ImageTk, ImageOps  # Para manejar imágenes

# Configuración
PAGE_SIZE = 30  # Número de elementos por página

# Clave secreta (la misma que en el API)
SECRET_KEY = b'LuNo7QH0oR3w9r3U9ZRCQ67UysCxg61Oa6HavzdSE1E='
fernet = Fernet(SECRET_KEY)

def decrypt_url(encrypted_url: str) -> str:
    """Desencripta la URL utilizando Fernet."""
    try:
        return fernet.decrypt(encrypted_url.encode()).decode()
    except Exception as e:
        messagebox.showerror("Error", f"Error al desencriptar la URL: {e}")
        return ""

def encrypt_url(url: str) -> str:
    """Encripta la URL utilizando Fernet."""
    try:
        return fernet.encrypt(url.encode()).decode()
    except Exception as e:
        messagebox.showerror("Error", f"Error al encriptar la URL: {e}")
        return ""

def adjust_server_url(url: str, server: str) -> str:
    """
    Ajusta la URL según el servidor.
    - Si server es "mega": reemplaza "mega.com" por "mega.nz".
    - Si server es "mediafire": se asegura que la URL incluya "mediafire.com".
    - Si server es "google drive": convierte el enlace compartido en un enlace de descarga directa.
    """
    server = server.lower()
    if server == "mega":
        return url.replace("mega.com", "mega.nz")
    elif server == "mediafire":
        if "mediafire" in url and "mediafire.com" not in url:
            return url.replace("mediafire", "mediafire.com")
        return url
    elif server == "google drive":
        if "drive.google.com" in url:
            if "uc?export=download" in url:
                return url
            parts = url.split("/d/")
            if len(parts) > 1:
                file_part = parts[1]
                file_id = file_part.split("/")[0]
                return f"https://drive.google.com/uc?export=download&id={file_id}"
        return url
    else:
        return url

def get_theme_from_settings() -> str:
    """
    Consulta la base de datos para obtener el tema actual desde el campo theme
    de la tabla settings. Si no se encuentra o hay error, se retorna 'flatly'.
    """
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

# Se consulta el tema antes de crear la ventana principal.
current_theme = get_theme_from_settings()

class Application(ttk.Window):
    def __init__(self):
        # Usamos el tema obtenido de la configuración (por defecto "flatly")
        super().__init__(themename=current_theme)
        self.title("Backup ROMs Free")
        self.geometry("900x600")
        self.resizable(False, False)
        # Agregamos un icono a la ventana principal (asegúrate de tener "icon.png")
        try:
            self.iconphoto(False, tk.PhotoImage(file="icon.png"))
        except Exception as e:
            pass
                
        # Ruta de descarga (por defecto, carpeta actual + "download")
        self.download_path = os.path.join(os.getcwd(), "download")
        print(self.download_path)
        
        # Cargar valores para los combos desde la base de datos
        consoles = self.load_consoles()
        regions = self.load_regions()
        
        # Variables para consola (tipo), búsqueda y región (por defecto "Todos")
        self.system = tk.StringVar(value="Todos")
        self.search_term = tk.StringVar()
        self.region = tk.StringVar(value="Todos")
        
        # Menú: Ahora agregamos dos opciones: Configuraciones y Actualizar BD
        menubar = tk.Menu(self)
        menubar.add_command(label="Configuraciones", command=self.open_settings_window)
        #menubar.add_command(label="Actualizar BD", command=self.open_crud_window)
        self.config(menu=menubar)
        
        # Frame superior: selección de consola, búsqueda y filtro por región
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
        
        # Variables de paginación y datos
        self.current_page = 1
        self.all_files = []
        
        # Diccionarios para almacenar imágenes PIL y PhotoImage para las banderas (región)
        self.region_pil = {}
        self.images = {}  # PhotoImage de región
        try:
            desired_size = (25, 15)
            for key, filename in {
                "australia": "australia.jpg",
                "default": "default.png",
                "denmark": "denmark.png",
                "europe": "europe.png",
                "france": "france.png",
                "germany": "germany.png",
                "italy": "italy.png",
                "japan": "japan.png",
                "korea": "korea.png",
                "netherlands": "netherlands.png",
                "norway": "norway.png",
                "portugal": "portugal.png",
                "russia": "russia.png",
                "scandinavia": "scandinavia.png",
                "spain": "spain.png",
                "sweden": "sweden.png",
                "uk": "uk.png",
                "usa": "usa.png"
            }.items():
                pil_img = Image.open(os.path.join("flags", filename)).resize(desired_size, Image.Resampling.LANCZOS)
                self.region_pil[key] = pil_img
                self.images[key] = ImageTk.PhotoImage(pil_img)
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar las imágenes de región: {e}")
        
        # Imágenes del servidor
        self.server_pil = {}
        self.server_images = {}
        try:
            server_size = (15, 15)
            pil_mega = Image.open(os.path.join("flags", "mega.png")).resize(server_size, Image.Resampling.LANCZOS)
            pil_other = Image.open(os.path.join("flags", "other.png")).resize(server_size, Image.Resampling.LANCZOS)
            self.server_pil["mega"] = pil_mega
            self.server_pil["otros"] = pil_other
            self.server_images["mega"] = ImageTk.PhotoImage(pil_mega)
            self.server_images["otros"] = ImageTk.PhotoImage(pil_other)
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar las imágenes del servidor: {e}")
        
        self.composite_images = {}
        
        # Configurar el Treeview.
        columns = ("Servidor", "Name", "Size", "Download")
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings")
        self.tree.heading("#0", text="Región")
        self.tree.heading("Servidor", text="Servidor")
        self.tree.heading("Name", text="Nombre")
        self.tree.heading("Size", text="Tamaño")
        self.tree.heading("Download", text="Descargar")
        
        self.tree.column("#0", width=60)
        self.tree.column("Servidor", width=60)
        self.tree.column("Name", width=350)
        self.tree.column("Size", width=100)
        self.tree.column("Download", width=50)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
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
        path = tk.filedialog.askdirectory(title="Selecciona la carpeta de descarga")
        if path:
            self.download_path = path
            messagebox.showinfo("Configuraciones", f"Ruta de descarga establecida: {self.download_path}")

    def open_settings_window(self):
        settings_win = tk.Toplevel(self)
        settings_win.title("Configuraciones")
        settings_win.geometry("400x300")
        settings_win.resizable(False, False)
        try:
            settings_win.iconphoto(False, tk.PhotoImage(file="icon.png"))
        except Exception as e:
            pass
        
        unzip_var = tk.BooleanVar()
        decryp_var = tk.BooleanVar()
        path_var = tk.StringVar()
        theme_var = tk.StringVar()
        theme_options = ["flatly", "litera", "darkly", "journal", "cyborg", "superhero", "minty", "pulse", "simplex", "vapor"]
        
        settings = self.load_settings()
        if settings is None:
            settings = {"unzip": "N", "path": os.path.join(os.getcwd(), "download"), "decryp": "N", "theme": "flatly"}
        unzip_var.set(True if settings["unzip"].upper() == "S" else False)
        path_var.set(settings["path"])
        decryp_var.set(True if settings["decryp"].upper() == "S" else False)
        theme_var.set(settings.get("theme", "flatly"))
        
        ttk.Label(settings_win, text="Descomprimir al finalizar la descarga:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Checkbutton(settings_win, variable=unzip_var).pack(anchor=tk.W, padx=20)
        
        ttk.Label(settings_win, text="Ruta de descarga:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Entry(settings_win, textvariable=path_var, width=70).pack(anchor=tk.W, padx=20)
        
        ttk.Label(settings_win, text="Encriptar:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Checkbutton(settings_win, variable=decryp_var).pack(anchor=tk.W, padx=20)
        
        ttk.Label(settings_win, text="Tema:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Combobox(settings_win, textvariable=theme_var, values=theme_options, state="readonly", width=68).pack(anchor=tk.W, padx=20)
        
        button_frame = ttk.Frame(settings_win)
        button_frame.pack(pady=30)
        def save_settings():
            unzip_val = "S" if unzip_var.get() else "N"
            download_path = path_var.get().strip() if path_var.get().strip() != "" else os.path.join(os.getcwd(), "download")
            decryp_val = "S" if decryp_var.get() else "N"
            theme_val = theme_var.get()
            self.update_settings(unzip_val, download_path, decryp_val, theme_val)
            messagebox.showinfo("Configuraciones", "Configuración actualizada.")
            settings_win.destroy()
        ttk.Button(button_frame, text="Guardar", command=save_settings).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancelar", command=settings_win.destroy).pack(side=tk.LEFT, padx=10)

    def load_settings(self):
        try:
            conn = sqlite3.connect("data/data.db")
            cursor = conn.cursor()
            cursor.execute("SELECT unzip, path, decryp, theme FROM settings LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row:
                return {"unzip": row[0], "path": row[1], "decryp": row[2], "theme": row[3]}
            else:
                return None
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar la configuración: {e}")
            return None
    
    def update_settings(self, unzip, path, decryp, theme):
        try:
            conn = sqlite3.connect("data/data.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM settings")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute("INSERT INTO settings (unzip, path, decryp, theme) VALUES (?, ?, ?, ?)", (unzip, path, decryp, theme))
            else:
                cursor.execute("UPDATE settings SET unzip=?, path=?, decryp=?, theme=?", (unzip, path, decryp, theme))
            conn.commit()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar la configuración: {e}")

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
        total_pages = math.ceil(total_items / PAGE_SIZE) if total_items > 0 else 1
        if self.current_page < 1:
            self.current_page = 1
        elif self.current_page > total_pages:
            self.current_page = total_pages
        
        start_index = (self.current_page - 1) * PAGE_SIZE
        end_index = start_index + PAGE_SIZE
        
        self.item_url_mapping = {}
        self.composite_images.clear()
        for file in self.all_files[start_index:end_index]:
            name, region_value, size, _type, url, encrypted, server_value = file
            comp_img = self.create_composite_image(region_value, server_value)
            key = f"{name}_{server_value}"
            self.composite_images[key] = comp_img
            item_id = self.tree.insert("", tk.END, text="", image=comp_img,
                                       values=(server_value, name, size, "Download"))
            self.item_url_mapping[item_id] = {"url": url, "name": name, "encrypted": encrypted, "server": server_value}
        
        self.page_info_label.config(text=f"Página {self.current_page} de {total_pages}")
        self.prev_btn.config(state=tk.DISABLED if self.current_page <= 1 else tk.NORMAL)
        self.next_btn.config(state=tk.DISABLED if self.current_page >= total_pages else tk.NORMAL)

    def on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if item_id and column == "#4":
            info = self.item_url_mapping.get(item_id)
            if info:
                if info["encrypted"].upper() == "S":
                    real_url = decrypt_url(info["url"])
                else:
                    real_url = info["url"]
                real_url = adjust_server_url(real_url, info["server"])
                file_name = info["name"]
                self.start_download(real_url, file_name)

    def start_download(self, url, file_name):
        download_win = tk.Toplevel(self)
        download_win.title(f"Descargando: {file_name}")
        download_win.geometry("400x200")
        download_win.resizable(False, False)
        try:
            download_win.iconphoto(False, tk.PhotoImage(file="icon.png"))
        except Exception as e:
            pass
        
        label_file = ttk.Label(download_win, text=f"Archivo: {file_name}")
        label_file.pack(pady=5)
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(download_win, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=20, pady=10)
        
        label_speed = ttk.Label(download_win, text="Velocidad: 0 KB/s")
        label_speed.pack(pady=5)
        
        label_eta = ttk.Label(download_win, text="Tiempo restante: 0 s")
        label_eta.pack(pady=5)
        
        file_path = os.path.join(self.download_path, file_name)
        
        def update_progress(downloaded, total, speed, remaining):
            percent = (downloaded / total) * 100 if total else 0
            progress_var.set(percent)
            label_speed.config(text=f"Velocidad: {speed/1024:.2f} KB/s")
            label_eta.config(text=f"Tiempo restante: {int(remaining)} s")
        
        def finish_download(success, info):
            if success:
                current_settings = self.load_settings()
                if file_name.lower().endswith('.zip') and current_settings and current_settings["unzip"].upper() == "S":
                    try:
                        extract_path = os.path.join(self.download_path, os.path.splitext(file_name)[0])
                        with zipfile.ZipFile(info, 'r') as zip_ref:
                            zip_ref.extractall(extract_path)
                        messagebox.showinfo("Descarga completada", f"Archivo guardado en:\n{info}\nDescomprimido en:\n{extract_path}")
                    except Exception as e:
                        messagebox.showerror("Error al descomprimir", f"Error al descomprimir el archivo: {e}")
                else:
                    messagebox.showinfo("Descarga completada", f"Archivo guardado en:\n{info}")
            else:
                messagebox.showerror("Error en descarga", f"Ocurrió un error:\n{info}")
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
        total_pages = math.ceil(total_items / PAGE_SIZE) if total_items > 0 else 1
        if self.current_page < total_pages:
            self.current_page += 1
            self.display_page()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.display_page()

    def open_crud_window(self):
        """Abre una ventana para insertar nuevos registros en la tabla files."""
        crud_win = tk.Toplevel(self)
        crud_win.title("Actualizar BD")
        crud_win.geometry("300x350")
        crud_win.resizable(False, False)
        try:
            crud_win.iconphoto(False, tk.PhotoImage(file="icon.png"))
        except Exception as e:
            pass

        # Campos para insertar:
        # Nombre (obligatorio)
        ttk.Label(crud_win, text="Nombre de la rom:").pack(anchor=tk.W, padx=10, pady=5)
        name_entry = ttk.Entry(crud_win, width=50)
        name_entry.pack(anchor=tk.W, padx=20)
        
        # Región (combo desde tabla region, default "Unknow")
        ttk.Label(crud_win, text="Región:").pack(anchor=tk.W, padx=10, pady=5)
        regions = self.load_regions()
        # Forzar valor por defecto "Unknow"
        if "Unknow" not in regions:
            regions.insert(0, "Unknow")
        region_var = tk.StringVar(value="Unknow")
        region_combo = ttk.Combobox(crud_win, textvariable=region_var, values=regions, state="readonly", width=47)
        region_combo.pack(anchor=tk.W, padx=20)
        
        # Peso y Unidad
        weight_frame = ttk.Frame(crud_win)
        weight_frame.pack(anchor=tk.W, padx=20, pady=5)
        ttk.Label(weight_frame, text="Peso:").pack(side=tk.LEFT)
        weight_entry = ttk.Entry(weight_frame, width=20)
        weight_entry.pack(side=tk.LEFT, padx=5)
        unit_var = tk.StringVar(value="MiB")
        unit_combo = ttk.Combobox(weight_frame, textvariable=unit_var, values=["MiB", "GiB"], state="readonly", width=10)
        unit_combo.pack(side=tk.LEFT)
        
        # Consola (combo desde tabla console, default primer registro)
        ttk.Label(crud_win, text="Consola:").pack(anchor=tk.W, padx=10, pady=5)
        consoles = self.load_consoles()
        default_console = consoles[0] if consoles else ""
        console_var = tk.StringVar(value=default_console)
        console_combo = ttk.Combobox(crud_win, textvariable=console_var, values=consoles, state="readonly", width=47)
        console_combo.pack(anchor=tk.W, padx=20)
        
        # URL (obligatorio)
        ttk.Label(crud_win, text="URL:").pack(anchor=tk.W, padx=10, pady=5)
        url_entry = ttk.Entry(crud_win, width=50)
        url_entry.pack(anchor=tk.W, padx=20)
        
        # Botón Insertar
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
            # Construir el campo size
            size = f"{weight} {unit}" if weight else ""
            # Consultar la configuración para el campo encrypted
            settings = self.load_settings()
            if settings and settings["decryp"].upper() == "S":
                encrypted_url = encrypt_url(url)
            else:
                encrypted_url = url
            server = "Otros"  # Valor por defecto
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
    
    # ... (los métodos fetch_data, create_composite_image, display_page, on_tree_click, start_download, next_page, prev_page son los mismos que ya están definidos) ...

    def next_page(self):
        total_items = len(self.all_files)
        total_pages = math.ceil(total_items / PAGE_SIZE) if total_items > 0 else 1
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
