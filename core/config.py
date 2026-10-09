import os
import pyaudio
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("api_key")
if not api_key:
    raise ValueError("API ключ не найден в .env")

HOTKEY = os.getenv("HOTKEY") or "x2"

CHUNK = int(os.getenv("CHUNK") or 1024)
FORMAT = pyaudio.paInt16
CHANNELS = int(os.getenv("CHANNELS") or 1)
RATE = int(os.getenv("RATE") or 16000)

raw_index = os.getenv("INPUT_DEVICE_INDEX", "-1")
INPUT_DEVICE_INDEX = int(raw_index)
INPUT_DEVICE_INDEX = INPUT_DEVICE_INDEX if INPUT_DEVICE_INDEX >= 0 else None

# --- VAD И ПАУЗЫ ---
# Базовый порог громкости для тишины
SILENCE_THRESHOLD = int(os.getenv("SILENCE_THRESHOLD") or 450)

# Коэффициент загрубления микрофона, когда бот сам говорит в динамики (чтобы не слышал себя)
SPEAKER_ECHO_MULTIPLIER = 2.4

# Сколько секунд молчания считать концом фразы (1.4 сек дает время подумать и вдохнуть)
SILENCE_DURATION = float(os.getenv("SILENCE_DURATION") or 3.5)

# Время удержания диалога (секунд): после ответа столько времени можно говорить без слова «Джарвис»
DIALOGUE_TIMEOUT = 60.0

# --- СЛОВАРЬ ТРИГГЕРОВ ---
WAKE_WORDS = ["джарвис", "jarvis"]
STOP_WORDS = ["стой", "стоп", "замолчи", "тихо", "хватит"]
SLEEP_WORDS = ["отбой", "завершение", "пока", "отключись", "спи"]