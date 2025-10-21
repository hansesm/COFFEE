import re
from abc import ABC, abstractmethod
from typing import Any, Dict

import math
from django.utils import translation
from pydantic import BaseModel

# BaseModel makes it easier to extend the structure
class TokenEstimate(BaseModel):
    tokens: int


class TokenEstimatorStrategy(ABC):
    """Interface for estimation strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique, short identifier for the strategy (e.g., 'heuristic')."""

    @abstractmethod
    def estimate(self, text: str, **kwargs: Any) -> TokenEstimate:
        """Return a TokenEstimate for the given text."""


LANG_BASELINE = {
    "de": 3.6,  # ~1 token per 3.6 chars (incl. whitespace)
    "en": 4.0,
}

class RoughStrategy(TokenEstimatorStrategy):
    """Fastest: estimate by total characters / chars_per_token.

    Good baseline for plain text. Optionally set chars_per_token directly
    or pick a language baseline.
    """

    def __init__(self, chars_per_token: int = None) -> None:
        language = translation.get_language()
        self._chars_per_token = LANG_BASELINE.get(language, 3.6)
        if chars_per_token:
            self._chars_per_token = chars_per_token
        self._language = language

    @property
    def name(self) -> str:
        return "rough"

    def estimate(self, text: str, **kwargs: Any) -> TokenEstimate:
        chars = len(text)
        tokens = math.ceil(chars / max(self._chars_per_token, 1e-9))
        return TokenEstimate(tokens=tokens)
