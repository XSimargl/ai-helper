import customtkinter as ctk
import threading
from core import config

class GUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Джарвис Голосовой Ассистент")
        self.geometry("650x750")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.header.grid_columnconfigure(1, weight=1)
        
        self.lbl_title = ctk.CTkLabel(self.header, text="J.A.R.V.I.S.", font=ctk.CTkFont(size=28, weight="bold"))
        self.lbl_title.grid(row=0, column=0, sticky="w")
        
        self.lbl_status = ctk.CTkLabel(self.header, text="Инициализация...", text_color="gray", font=ctk.CTkFont(size=16))
        self.lbl_status.grid(row=0, column=1, sticky="e")
        
        self.textbox = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(size=15), corner_radius=10)
        self.textbox.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.textbox.configure(state="disabled")
        
        # --- НОВАЯ ПАНЕЛЬ С КНОПКАМИ ---
        # Создаем контейнер, в котором будут лежать все 3 кнопки в ряд
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        # Настраиваем ширину: кнопка микрофона занимает 2 части, остальные по 1 части
        self.controls_frame.grid_columnconfigure(0, weight=2) 
        self.controls_frame.grid_columnconfigure(1, weight=1)
        self.controls_frame.grid_columnconfigure(2, weight=1)
        
        self.btn_mic = ctk.CTkButton(
            self.controls_frame, 
            text=f"🎤 Сказать (или '{config.HOTKEY}')", 
            height=50,                                        
            corner_radius=10,                                
            font=ctk.CTkFont(size=16, weight="bold"),         
            command=self.on_mic_click,                        
            fg_color="#0056b3",                               
            hover_color="#004494"                             
        )
        self.btn_mic.grid(row=0, column=0, padx=(0, 10), sticky="ew") 
        
        # Флаг состояния паузы
        self.is_paused = False
        
        # Кнопка ПАУЗЫ
        self.btn_pause = ctk.CTkButton(
            self.controls_frame, 
            text="⏸️ Пауза", 
            height=50,                                        
            corner_radius=10,                                
            font=ctk.CTkFont(size=16, weight="bold"),         
            command=self.toggle_pause,                        
            fg_color="#d39e00",   # Желто-оранжевый цвет                           
            hover_color="#b8860b"                             
        )
        self.btn_pause.grid(row=0, column=1, padx=(0, 10), sticky="ew")

        # Кнопка ВЫКЛЮЧЕНИЯ
        self.btn_exit = ctk.CTkButton(
            self.controls_frame, 
            text="❌ Выход", 
            height=50,                                        
            corner_radius=10,                                
            font=ctk.CTkFont(size=16, weight="bold"),         
            command=self.on_exit_click,                        
            fg_color="#dc3545",  # Красный цвет                           
            hover_color="#c82333"                             
        )
        self.btn_exit.grid(row=0, column=2, sticky="ew")
        
        self.mic_clicked_event = threading.Event()
        self.on_close_callback = None  # Сюда main.py передаст системную функцию закрытия

    def on_mic_click(self):
        self.mic_clicked_event.set() 
        
    def toggle_pause(self):
        """Включает и выключает паузу, меняет цвет кнопки и статус"""
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.configure(text="▶️ Включить", fg_color="#28a745", hover_color="#218838")
            self.safe_update_status("Пауза (микрофон отключен)", "#dc3545")
        else:
            self.btn_pause.configure(text="⏸️ Пауза", fg_color="#d39e00", hover_color="#b8860b")
            self.safe_update_status("Ожидание...", "gray")

    def on_exit_click(self):
        """Вызывает правильное закрытие приложения (вместе с ИИ и звуком)"""
        if self.on_close_callback:
            self.on_close_callback()
        else:
            self.destroy()

    def safe_update_status(self, text, color="gray"):
        self.after(0, lambda: self.lbl_status.configure(text=text, text_color=color))

    def safe_append_text(self, role, text=""):
        def _append():
            self.textbox.configure(state="normal") 
            
            if role == "user":
                self.textbox.insert("end", f"🗣 Вы:\n{text}\n\n") 
            elif role == "jarvis":
                self.textbox.insert("end", f"🤖 Джарвис:\n")      
            elif role == "chunk":
                self.textbox.insert("end", f"{text} ")          
            elif role == "end":
                self.textbox.insert("end", "\n\n")               
            elif role == "system":
                self.textbox.insert("end", f"⚙️ [{text}]\n\n")    
                
            self.textbox.configure(state="disabled") 
            self.textbox.yview("end")                
            
        self.after(0, _append)