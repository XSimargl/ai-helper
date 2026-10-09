import time
from collections import deque
import numpy as np
import pyaudio
from core import config


class AudioRecorder:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self._init_stream()

    def _init_stream(self):
        self.stream = self.p.open(
            format=config.FORMAT,
            channels=config.CHANNELS,
            rate=config.RATE,
            input=True,
            input_device_index=config.INPUT_DEVICE_INDEX,
            frames_per_buffer=config.CHUNK
        )

    def listen_phrase(self, check_button_callback=None, is_speaker_playing_callback=None, timeout=None):
        """
        Слушает микрофон.
        - timeout: максимальное время ожидания начала фразы (для сессии диалога).
        - check_button_callback: проверка клика кнопки мыши.
        - is_speaker_playing_callback: глушит микрофон, пока говорят колонки.
        """
        pre_chunks = int(0.35 * config.RATE / config.CHUNK)
        pre_buffer = deque(maxlen=pre_chunks)

        recorded_frames = []
        is_speaking = False
        silence_start_time = None
        triggered_by_button = False
        waiting_speech_after_button = False
        button_press_time = 0
        listen_start_time = time.time()

        while True:
            # 1. Проверка клика кнопки мыши
            if check_button_callback and check_button_callback():
                triggered_by_button = True
                waiting_speech_after_button = True
                button_press_time = time.time()
                pre_buffer.clear()
                recorded_frames.clear()

            try:
                data = self.stream.read(config.CHUNK, exception_on_overflow=False)
            except Exception:
                continue

            # 2. Игнорирование звука из динамиков
            if is_speaker_playing_callback and is_speaker_playing_callback():
                if not triggered_by_button:
                    pre_buffer.clear()
                    continue

            audio_data = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))

            # 3. Режим кнопки: ждем начала речи пользователя
            if waiting_speech_after_button:
                if rms > config.SILENCE_THRESHOLD:
                    waiting_speech_after_button = False
                    is_speaking = True
                    silence_start_time = None
                    recorded_frames.append(data)
                elif time.time() - button_press_time > 4.5:
                    # Кнопку нажали, но ничего не сказали за 4.5 сек
                    return None, True
                continue

            # 4. Проверка таймаута сессии диалога (если речь ещё не началась)
            if not is_speaking and timeout is not None:
                if time.time() - listen_start_time > timeout:
                    return None, False

            # 5. Обычное отслеживание речи (VAD)
            if not is_speaking:
                pre_buffer.append(data)
                if rms > config.SILENCE_THRESHOLD:
                    is_speaking = True
                    silence_start_time = None
                    recorded_frames.extend(pre_buffer)
                    recorded_frames.append(data)
            else:
                recorded_frames.append(data)
                if rms < config.SILENCE_THRESHOLD:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                    elif time.time() - silence_start_time > config.SILENCE_DURATION:
                        # Пауза выдержана — фраза закончена
                        break
                else:
                    silence_start_time = None

        audio_bytes = b''.join(recorded_frames)
        # Фильтрация случайных щелчков короче 0.35 сек
        if len(audio_bytes) < config.RATE * 0.35:
            return None, triggered_by_button

        return audio_bytes, triggered_by_button

    def close(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()


def list_audio_devices():
    p = pyaudio.PyAudio()
    print("Список аудиоустройств:")
    try:
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                print(f"{i}: {dev['name']} (Input Channels: {dev['maxInputChannels']})")
    finally:
        p.terminate()