from typing import Optional, Tuple, Iterable, Callable

from coffee.home.ai_provider.models import CoffeeUsage


class AIBaseClient:
    def test_connection(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        pass

    def stream(self, llm_model: "LLMModel", user_input: str, system_prompt: str,
               on_usage_report: Optional[Callable[[CoffeeUsage], None]] = None, ) -> Iterable[str]:
        pass