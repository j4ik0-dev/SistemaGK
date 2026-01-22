import customtkinter as ctk
import subprocess
import json
import threading
import time

DEVICE_NAME_FILTER = "GK-994W" 
REFRESH_RATE = 60          
APP_SIZE = "300x180"           

ctk.set_appearance_mode("Dark") 
ctk.set_default_color_theme("blue")

class BatteryMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Xtrike Monitor")
        self.geometry(APP_SIZE)
        self.resizable(False, False)
        
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3), weight=1)

        self.lbl_title = ctk.CTkLabel(self, text="Xtrike Me GK-994W", font=("Roboto Medium", 16))
        self.lbl_title.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="ew")

        self.lbl_percent = ctk.CTkLabel(self, text="--%", font=("Roboto", 40, "bold"), text_color="#3B8ED0")
        self.lbl_percent.grid(row=1, column=0, padx=20, pady=5)

        self.progress_bar = ctk.CTkProgressBar(self, width=200, height=15)
        self.progress_bar.grid(row=2, column=0, padx=20, pady=10)
        self.progress_bar.set(0)

        self.lbl_status = ctk.CTkLabel(self, text="Buscando dispositivo...", font=("Roboto", 12), text_color="gray")
        self.lbl_status.grid(row=3, column=0, padx=20, pady=(0, 20))

        self.running = True
        self.monitor_thread = threading.Thread(target=self.loop_check_battery, daemon=True)
        self.monitor_thread.start()

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
            
            result = subprocess.check_output(
                ["powershell", "-Command", ps_command], 
                text=True, 
                startupinfo=startupinfo
            )
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
                    self.update_ui(level, connected=True)
                    found = True
                    break
            
            if not found:
                self.update_ui(0, connected=False)
            
            time.sleep(REFRESH_RATE)

    def update_ui(self, level, connected):
        if connected:
            self.lbl_percent.configure(text=f"{level}%", text_color="#3B8ED0" if level > 20 else "#E53935")
            self.progress_bar.set(level / 100)
            
            color = "#3B8ED0" # Azul normal
            status_text = "Conectado por Bluetooth"
            
            if level <= 20:
                color = "#E53935" # Rojo alerta
                status_text = "⚠️ Batería Baja - Conecta el cable"
            
            self.progress_bar.configure(progress_color=color)
            self.lbl_status.configure(text=status_text, text_color="white")
        else:
            self.lbl_percent.configure(text="--%", text_color="gray")
            self.progress_bar.set(0)
            self.lbl_status.configure(text="Modo 2.4G / Cable / Desconectado", text_color="gray")

if __name__ == "__main__":
    app = BatteryMonitorApp()
    app.mainloop()