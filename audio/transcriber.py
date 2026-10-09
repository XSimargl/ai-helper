import numpy as np
from faster_whisper import WhisperModel
from core import config
import torch

class speechRecognizer:
    def __init__(self):
        print("Загружаю мозг Whisper...")
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            self.model = WhisperModel("large-v3-turbo", device=device, compute_type=compute_type)
            print("\n=== ГОТОВО ===")
        except Exception as e:
            print(f"Ошибка при загрузке модели: {e}")
            self.model = None

    def process_audio(self, raw_data):
        if self.model is None:
            print("Модель не загружена. Невозможно распознать аудио.")
            return None
        if len(raw_data) < config.RATE:
            print("Слишком короткое нажатие, удерживай кнопку дольше.")
            return None
        try:
            audio_numpy = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            segments, info = self.model.transcribe(
                audio_numpy,
                beam_size=5,
                vad_filter=True,
                language="ru"
            )
            
            text = ""
            for segment in segments:
                text += segment.text + " "
            
            return text.strip()
        except Exception as e:
            print(f"Ошибка при распознавании аудио: {e}")
            return None
