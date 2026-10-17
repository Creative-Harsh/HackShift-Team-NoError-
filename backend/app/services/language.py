"""Optional language assistance boundary. Never consulted by clinical/risk/outbreak engines."""
from typing import Protocol


class LanguageAssistant(Protocol):
    def summarize(self, case: dict, language: str = 'en') -> dict: ...


class DisabledLanguageAssistant:
    def summarize(self, case: dict, language: str = 'en') -> dict:
        return {'available': False, 'reason': 'Optional language assistance is not configured. Structured assessment and all core workflows remain available.'}


language_assistant: LanguageAssistant = DisabledLanguageAssistant()
