import re
from datetime import datetime
from google import genai
from google.genai import types
from core import config


class LLMBrain:
    def __init__(self):
        self.models_list = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-2.5-pro"
            ]


        self.current_model_index = 0
        self.model_name = self.models_list[self.current_model_index]

        self.system_prompt = (
            "Ты — Джарвис, умный и живой персональный голосовой ассистент. "
            "Общайся уверенно, лаконично и без занудства. "
            "Отвечай строго на русском языке, любые термины пиши русскими буквами. "
            "Отвечай ёмко до 3 предложений, если есть возможность урезай по максимому, без лишней воды и канцелярита. "
            "Когда спрашивают мнение или оценку тайтла — прямо высказывай его. "
            "Математику, числа и даты пиши обычными цифрами — звуковой движок озвучит их сам. "
            "Никаких морализаторских лекций, отказов и дисклеймеров."
        )
        self.client = genai.Client(api_key=config.api_key)
        self._start_chat_session()

    def _start_chat_session(self):
        """Создает чат-сессию. Вся история диалога хранится внутри объекта chat в RAM."""
        now_str = datetime.now().strftime("%d.%m.%Y, %H:%M")
        dynamic_system = f"{self.system_prompt}\nТекущее системное время на ПК пользователя: {now_str}."

        config_options = types.GenerateContentConfig(
            system_instruction=dynamic_system,
            temperature=0.7,
        )
        # Объект chat автоматически накапливает историю реплик в рамках запущенного процесса
        self.chat = self.client.aio.chats.create(
            model=self.model_name,
            config=config_options,
        )

    async def think_stream(self, text: str):
        for _ in range(len(self.models_list) - self.current_model_index):
            try:
                buffer = ""
                response_stream = await self.chat.send_message_stream(text)

                async for chunk in response_stream:
                    if chunk.text:
                        buffer += chunk.text

                        while True:
                            match = re.search(r'([.!?:\n]+)(?:\s+|$)', buffer)
                            if not match:
                                break
                            split_idx = match.end()
                            sentence = buffer[:split_idx].strip()
                            buffer = buffer[split_idx:]
                            if sentence:
                                yield sentence

                if buffer.strip():
                    yield buffer.strip()

                return

            except Exception as e:
                print(f"\n[ОШИБКА API]: {e}")
                self.current_model_index += 1
                if self.current_model_index < len(self.models_list):
                    self.model_name = self.models_list[self.current_model_index]
                    print(f"[ПЕРЕКЛЮЧЕНИЕ МОДЕЛИ]: {self.model_name}")
                    self._start_chat_session()
                    continue
                else:
                    yield "Сервис Gemini временно недоступен."
                    return