import customtkinter as ctk
import subprocess
import json
import threading
import time
from PIL import Image, ImageDraw
import pystray
from winotify import Notification, audio

# --- CONFIGURACIÓN ---
DEVICE_NAME_FILTER = "GK-994W"
REFRESH_RATE = 60  # Segundos
APP_SIZE = "300x180"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class BatteryMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de ventana
        self.title("Xtrike Monitor")
        self.geometry(APP_SIZE)
        self.resizable(False, False)
        
        # Interceptar el botón de cierre "X"
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        # UI Elements
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3), weight=1)

        self.lbl_title = ctk.CTkLabel(self, text="Xtrike Me GK-994W", font=("Segoe UI", 16))
        self.lbl_title.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="ew")

        self.lbl_percent = ctk.CTkLabel(self, text="--%", font=("Segoe UI", 40, "bold"), text_color="#3B8ED0")
        self.lbl_percent.grid(row=1, column=0, padx=20, pady=5)

        self.progress_bar = ctk.CTkProgressBar(self, width=200, height=15)
        self.progress_bar.grid(row=2, column=0, padx=20, pady=10)
        self.progress_bar.set(0)

        self.lbl_status = ctk.CTkLabel(self, text="Iniciando...", font=("Segoe UI", 12), text_color="gray")
        self.lbl_status.grid(row=3, column=0, padx=20, pady=(0, 20))

        # Estado interno
        self.running = True
        self.last_notified = False # Para no spamear notificaciones
        self.tray_icon = None

        # Iniciar hilo de monitoreo
        self.monitor_thread = threading.Thread(target=self.loop_check_battery, daemon=True)
        self.monitor_thread.start()
        
        # Iniciar hilo del icono de bandeja (Tray)
        self.tray_thread = threading.Thread(target=self.setup_tray_icon, daemon=True)
        self.tray_thread.start()

    # --- LÓGICA DE INTERFAZ Y TRAY ---
    def minimize_to_tray(self):
        self.withdraw() # Ocultar ventana
        # Opcional: Mostrar una notificación rápida avisando que sigue corriendo
        # self.send_notification("Xtrike Monitor", "La app sigue corriendo en segundo plano.")

    def show_window(self):
        self.deiconify() # Mostrar ventana
        self.lift()

    def quit_app(self):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()

    def create_icon_image(self, color="white"):
        # Generamos un icono simple con código (Un cuadrado con un rayo)
        # para no depender de archivos .ico externos
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), (30, 30, 30))
        dc = ImageDraw.Draw(image)
        # Dibujar batería
        dc.rectangle([16, 20, 48, 44], outline=color, width=3)
        dc.rectangle([48, 26, 52, 38], fill=color) # La punta
        # Relleno (simbólico)
        dc.rectangle([20, 24, 40, 40], fill=color)
        return image

    def setup_tray_icon(self):
        image = self.create_icon_image("#3B8ED0")
        menu = pystray.Menu(
            pystray.MenuItem("Abrir", lambda: self.after(0, self.show_window), default=True),
            pystray.MenuItem("Salir", lambda: self.after(0, self.quit_app))
        )
        self.tray_icon = pystray.Icon("XtrikeBattery", image, "Xtrike Monitor", menu)
        self.tray_icon.run()

    # --- LÓGICA DE NOTIFICACIONES ---
    def send_notification(self, title, msg, is_alert=False):
        toast = Notification(
            app_id="Xtrike Monitor",
            title=title,
            msg=msg,
            duration="short",
            icon="" 
        )
        if is_alert:
            toast.set_audio(audio.LoopingAlarm, loop=False)
        else:
            toast.set_audio(audio.Default, loop=False)
        toast.show()

    # --- LÓGICA DE BATERÍA ---
    def get_battery_powershell(self):
        ps_command = """
        Get-PnpDevice -Class 'Bluetooth' | ForEach-Object {
            $dev = $_
            $bat = Get-PnpDeviceProperty -KeyName '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' -InstanceId $dev.InstanceId -ErrorAction SilentlyContinue
            if ($bat) {
                @{ Name = $dev.FriendlyName; Battery = $bat.Data }
            }
        } | ConvertTo-Json
        """
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.check_output(["powershell", "-Command", ps_command], text=True, startupinfo=startupinfo)
            if not result or result.strip() == "": return []
            data = json.loads(result)
            return [data] if isinstance(data, dict) else data
        except Exception:
            return []

    def loop_check_battery(self):
        while self.running:
            devices = self.get_battery_powershell()
            found = False
            
            for d in devices:
                name = d.get('Name', '')
                level = d.get('Battery')
                
                if DEVICE_NAME_FILTER in name and isinstance(level, int):
                    self.after(0, self.update_ui, level, True)
                    
                    # Lógica de Alerta de Batería Baja
                    if level <= 20 and not self.last_notified:
                        self.send_notification("¡Batería Baja!", f"Tu teclado está al {level}%. Conecta el cable.", is_alert=True)
                        self.last_notified = True
                    elif level > 20:
                        self.last_notified = False # Resetear alerta si se cargó
                    
                    found = True
                    break
            
            if not found:
                self.after(0, self.update_ui, 0, False)
            
            time.sleep(REFRESH_RATE)

    def update_ui(self, level, connected):
        if connected:
            color = "#3B8ED0" if level > 20 else "#E53935"
            self.lbl_percent.configure(text=f"{level}%", text_color=color)
            self.progress_bar.set(level / 100)
            self.progress_bar.configure(progress_color=color)
            self.lbl_status.configure(text="Conectado vía Bluetooth", text_color="white")
        else:
            self.lbl_percent.configure(text="--%", text_color="gray")
            self.progress_bar.set(0)
            self.lbl_status.configure(text="Modo 2.4G / Cable / Desconectado", text_color="gray")

if __name__ == "__main__":
    app = BatteryMonitorApp()
    app.mainloop()