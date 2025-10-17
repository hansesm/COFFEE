from typing import Dict

from pydantic import BaseModel, Field


class CoffeeUsage(BaseModel):
    tokens_used_system: int = Field(default=0)
    tokens_used_user: int = Field(default=0)
    tokens_used_completion: int = Field(default=0)
    total_duration_ns: int = Field(default=0)

class OllamaUsage(BaseModel):
    prompt_eval_count: int = Field(default=0)
    eval_count: int = Field(default=0)
    total_duration_ns: int = Field(default=0)
    prompt_duration_ns: int = Field(default=0)

    @classmethod
    def from_ollama_payload(cls, payload: Dict) -> "OllamaUsage":
        return cls(
            prompt_eval_count=payload.get("prompt_eval_count", 0),
            eval_count=payload.get("eval_count", 0),
            total_duration_ns=payload.get("total_duration", 0),
            prompt_duration_ns=payload.get("prompt_eval_duration", 0),
        )