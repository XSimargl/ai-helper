import os
import json
from google import genai
from google.genai import types
from core import config

class Hand_LLM:
    def get_time(self) -> str:
        """Возвращает текущее локальное время в формате ЧЧ:ММ."""
        from datetime import datetime
        return datetime.now().strftime("%H:%M")
