import os
import sys
import time
import argparse
import asyncio
import traceback
import re
import threading
import mouse

from core import config
from audio.recorder import AudioRecorder, list_audio_devices
from audio.transcriber import speechRecognizer
from core.brain import LLMBrain
from tools.speaker import Voice
from gui import GUI

voice = Voice(speaker="aidar", sample_rate=48000, device="cpu")


class MouseButtonTracker:
    def __init__(self, target_button: str):
        self.target_button = target_button.lower()
        self.clicked_event = threading.Event()
        try:
            mouse.hook(self._on_mouse_event)
        except Exception as e:
            print(f"[ВНИМАНИЕ]: Не удалось привязать хук мыши: {e}")

    def _on_mouse_event(self, event):
        if isinstance(event, mouse.ButtonEvent):
            if event.event_type == 'down' and str(event.button).lower() == self.target_button:
                self.clicked_event.set()

    def check_and_reset(self) -> bool:
        if self.clicked_event.is_set():
            self.clicked_event.clear()
            return True
        try:
            if mouse.is_pressed(self.target_button):
                return True
        except Exception:
            pass
        return False


btn_tracker = MouseButtonTracker(config.HOTKEY)


def check_hotkey_clicked(gui: GUI) -> bool:
    if btn_tracker.check_and_reset():      
        return True
    if gui.mic_clicked_event.is_set():     
        gui.mic_clicked_event.clear()      
        return True
    return False


def setup_cli():
    parser = argparse.ArgumentParser(description="Джарвис Голосовой Ассистент")
    parser.add_argument("--list-devices", action="store_true", help="Список аудиоустройств")
    parser.add_argument("--text", type=str, help="Прямой текстовый запрос")
    return parser.parse_args()


def match_command(text: str, words_list: list) -> bool:
    clean = re.sub(r'[^\w\s]', '', text.lower()).strip()
    tokens = clean.split()
    return any(word in tokens for word in words_list)


def extract_wake_word(text: str) -> tuple[bool, str]:
    pattern = r'\b(' + '|'.join(config.WAKE_WORDS) + r')\b'
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return False, ""
    clean_query = re.sub(r'^.*?\b(' + '|'.join(config.WAKE_WORDS) + r')\b[,.!?\s]*', '', text, flags=re.IGNORECASE).strip()
    return True, clean_query


async def stream_and_speak(brain: LLMBrain, query_text: str, gui: GUI) -> bool:
    try:
        t0 = time.time()
        first_chunk = True
        gui.safe_append_text("jarvis")

        async for sentence in brain.think_stream(query_text):
            if voice.interrupted.is_set():
                return False
            if first_chunk:
                print(f"[LLM Отклик]: {time.time() - t0:.2f} сек.")
                first_chunk = False
                
            gui.safe_append_text("chunk", sentence)
            voice.speak(sentence)

        gui.safe_append_text("end")

        while voice.is_speaking:
            if check_hotkey_clicked(gui):
                voice.stop()
                gui.safe_append_text("system", "Речь прервана пользователем")
                return False
            await asyncio.sleep(0.04)

        return True

    except asyncio.CancelledError:
        voice.stop()
        return False


async def main_async(gui: GUI):
    args = setup_cli()
    if args.list_devices:
        list_audio_devices()
        return

    gui.safe_update_status("Загрузка мозга LLM...", "#ffc107")
    brain = LLMBrain()

    if args.text:
        gui.safe_append_text("user", args.text)
        await stream_and_speak(brain, args.text, gui)
        voice.wait_until_done()
        return

    gui.safe_update_status("Загрузка аудио...", "#ffc107")
    recorder = AudioRecorder()
    transcriber = speechRecognizer()

    in_dialogue = False
    dialogue_deadline = 0

    welcome_text = (
        f"ДЖАРВИС АКТИВЕН\n"
        f"• Голос: скажи «Джарвис, ...» (сессия 10 сек).\n"
        f"• Клик: нажми «{config.HOTKEY}» или кнопку микрофона.\n"
        f"• Пауза: блокирует микрофон.\n"
        f"• Отбой: скажи «Отбой» или «Завершение»."
    )
    gui.safe_append_text("system", welcome_text)
    gui.safe_update_status("Ожидание...", "gray")

    while True:
        try:
            # --- НОВАЯ ЛОГИКА ПАУЗЫ ---
            if gui.is_paused:
                in_dialogue = False # Сбрасываем сессию, если включили паузу
                
                # Позволяем выйти из паузы нажатием горячей клавиши или экранной кнопки
                if check_hotkey_clicked(gui):
                    gui.toggle_pause() # Снимает паузу
                    gui.safe_append_text("system", "Пауза снята, микрофон активен")
                    await asyncio.sleep(0.3) # Ждем, чтобы клик не "залип"
                else:
                    await asyncio.sleep(0.2) # Просто спим и не тратим ресурсы ПК
                continue # Возвращаемся в начало цикла, ИГНОРИРУЯ микрофон

            current_time = time.time()
            session_timeout = None

            if in_dialogue:
                time_left = dialogue_deadline - current_time
                if time_left <= 0:
                    in_dialogue = False
                    gui.safe_update_status("Спящий режим", "gray")
                    gui.safe_append_text("system", "Сессия закрыта. Жду вызов.")
                else:
                    session_timeout = time_left
                    gui.safe_update_status(f"Слушаю ({int(time_left)}с)...", "#28a745")
            else:
                gui.safe_update_status("Ожидание...", "gray")

            raw_audio, by_button = await asyncio.to_thread(
                recorder.listen_phrase,
                lambda: check_hotkey_clicked(gui),
                lambda: voice.is_speaking,
                session_timeout
            )

            if raw_audio is None:
                if by_button:
                    gui.safe_update_status("Голос не обнаружен", "#dc3545")
                elif in_dialogue and session_timeout is not None:
                    in_dialogue = False
                    gui.safe_update_status("Спящий режим", "gray")
                    gui.safe_append_text("system", "Сессия диалога закрыта по таймауту")
                continue

            gui.safe_update_status("Распознавание...", "#ffc107")
            text = await asyncio.to_thread(transcriber.process_audio, raw_audio)
            
            if not text or len(text.strip()) < 2:
                continue

            if match_command(text, config.STOP_WORDS):
                voice.stop()
                gui.safe_append_text("system", f"СТОП: «{text}»")
                dialogue_deadline = time.time() + config.DIALOGUE_TIMEOUT
                in_dialogue = True
                continue

            if match_command(text, config.SLEEP_WORDS):
                voice.stop()
                in_dialogue = False
                gui.safe_append_text("system", f"ОТБОЙ: «{text}»")
                voice.speak("Отключаюсь.")
                continue

            has_wake_word, wake_query = extract_wake_word(text)
            should_run = False
            final_query = ""

            if by_button:
                should_run = True
                final_query = text
            elif has_wake_word:
                should_run = True
                if wake_query:
                    final_query = wake_query
                else:
                    gui.safe_update_status("Слушаю...", "#28a745")
                    voice.speak("Слушаю.")
                    while voice.is_speaking:
                        await asyncio.sleep(0.04)
                    dialogue_deadline = time.time() + config.DIALOGUE_TIMEOUT
                    in_dialogue = True
                    continue
            elif in_dialogue:
                should_run = True
                final_query = text

            if should_run and final_query:
                gui.safe_append_text("user", final_query)
                gui.safe_update_status("Генерация ответа...", "#007bff")
                
                await stream_and_speak(brain, final_query, gui)

                dialogue_deadline = time.time() + config.DIALOGUE_TIMEOUT
                in_dialogue = True

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[ОШИБКА ЦИКЛА]: {e}")
            traceback.print_exc()

    recorder.close()
    voice.close()


def start_async_loop(gui):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_async(gui))


def main():
    try:
        gui = GUI()
        threading.Thread(target=start_async_loop, args=(gui,), daemon=True).start()

        def on_closing():
            """Эта функция срабатывает при нажатии кнопки ❌ Выход ИЛИ крестика окна"""
            voice.close()
            gui.destroy()
            os._exit(0)
        
        gui.protocol("WM_DELETE_WINDOW", on_closing) # Закрытие по системному крестику
        gui.on_close_callback = on_closing           # Закрытие по нашей кнопке "Выход"
        
        gui.mainloop()
        
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()