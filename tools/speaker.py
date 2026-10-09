import os
import re
import queue
import threading
import time
import torch
import numpy as np
import pyaudio
from num2words import num2words

torch.set_num_threads(4)


class Voice:
    def __init__(self, speaker: str = "aidar", sample_rate: int = 48000, device: str = "cpu"):
        self.speaker = speaker
        self.sample_rate = sample_rate
        self.volume = 0.75
        self.speed = 1.15
        self.device = torch.device(device)

        print(f"[TTS] Загрузка Silero TTS v5 на {self.device}...")
        self.model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language="ru",
            speaker="v5_ru",
            trust_repo=True
        )
        self.model.to(self.device)
        print("[TTS] Модель Silero TTS v5 готова к работе.")

        self.text_queue = queue.Queue()
        self.audio_queue = queue.Queue()

        self.is_playing = False
        self.interrupted = threading.Event()
        self.last_audio_time = 0

        self.p = pyaudio.PyAudio()
        self.audio_stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=int(self.sample_rate * self.speed),
            output=True
        )

        threading.Thread(target=self._synthesis_worker, daemon=True).start()
        threading.Thread(target=self._playback_worker, daemon=True).start()

    @property
    def is_speaking(self) -> bool:
        """True, если есть текст в очереди, звук генерируется, играет или затухает эхо."""
        return (
            not self.text_queue.empty()
            or not self.audio_queue.empty()
            or self.is_playing
            or (time.time() - self.last_audio_time < 0.4)
        )

    def _clean_text(self, text: str) -> str:
        def replace_num(match):
            try:
                return num2words(int(match.group()), lang='ru')
            except Exception:
                return match.group()

        text = re.sub(r'\b\d+\b', replace_num, text)
        text = re.sub(r'[*#_`~>\[\]\(\)\{\}]', '', text)
        text = text.replace('%', ' процентов ').replace('$', ' долларов ')
        return re.sub(r'\s+', ' ', text).strip()

    def speak(self, text: str):
        clean = self._clean_text(text)
        if not clean or not re.search(r'[a-zA-Zа-яА-ЯёЁ0-9]', clean):
            return
        print(f"[ДЖАРВИС]: {clean}")
        self.text_queue.put(clean)

    def stop(self):
        """Мгновенно прерывает воспроизведение и очищает все очереди."""
        self.interrupted.set()

        while not self.text_queue.empty():
            try:
                self.text_queue.get_nowait()
                self.text_queue.task_done()
            except Exception:
                break

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
            except Exception:
                break

        self.is_playing = False
        self.last_audio_time = time.time()
        time.sleep(0.04)
        self.interrupted.clear()

    def _synthesis_worker(self):
        while True:
            text = self.text_queue.get()
            if self.interrupted.is_set():
                self.text_queue.task_done()
                continue

            try:
                with torch.inference_mode():
                    audio_tensor = self.model.apply_tts(
                        text=text,
                        speaker=self.speaker,
                        sample_rate=self.sample_rate,
                        put_accent=True,
                        put_yo=True
                    )

                audio_numpy = (audio_tensor.detach().cpu().numpy() * self.volume * 32767).clip(-32768, 32767).astype(np.int16)
                audio_bytes = audio_numpy.tobytes()

                if not self.interrupted.is_set():
                    self.audio_queue.put(audio_bytes)
            except Exception as e:
                print(f"\n[ОШИБКА СИНТЕЗА]: {e}\n")
            finally:
                self.text_queue.task_done()

    def _playback_worker(self):
        chunk_size = 2048
        while True:
            audio_data = self.audio_queue.get()
            if self.interrupted.is_set():
                self.audio_queue.task_done()
                continue

            self.is_playing = True
            try:
                for i in range(0, len(audio_data), chunk_size):
                    if self.interrupted.is_set():
                        break
                    self.audio_stream.write(audio_data[i:i + chunk_size])
            except Exception as e:
                print(f"\n[ОШИБКА ВЫВОДА ЗВУКА]: {e}\n")
            finally:
                self.last_audio_time = time.time()
                self.is_playing = False
                self.audio_queue.task_done()

    def wait_until_done(self):
        self.text_queue.join()
        self.audio_queue.join()

    def close(self):
        try:
            self.stop()
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.p.terminate()
        except Exception:
            pass