from collections import defaultdict
from typing import Dict, List


class ChatMemory:
    """
    Хранит:
    - историю сообщений по chat_id
    - текущий режим (prompt mode) по chat_id
    """

    def __init__(self, max_history: int, default_mode: str):
        self.max_history = max_history
        self.default_mode = default_mode

        self.histories: Dict[int, List[dict]] = defaultdict(list)
        self.modes: Dict[int, str] = {}

    def get_mode(self, chat_id: int) -> str:
        return self.modes.get(chat_id, self.default_mode)

    def set_mode(self, chat_id: int, mode_key: str) -> None:
        self.modes[chat_id] = mode_key

    def reset_history(self, chat_id: int) -> None:
        self.histories[chat_id] = []

    def add_message(self, chat_id: int, role: str, content: str) -> None:
        self.histories[chat_id].append({
            "role": role,
            "content": content
        })

        # Оставляем только последние max_history сообщений
        if len(self.histories[chat_id]) > self.max_history:
            self.histories[chat_id] = self.histories[chat_id][-self.max_history:]

    def get_history(self, chat_id: int, limit: int | None = None) -> List[dict]:
        history = self.histories.get(chat_id, [])
        if limit is not None:
            return history[-limit:]
        return history