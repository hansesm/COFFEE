from typing import Optional, Tuple, List, Dict, Iterable, Callable

from coffee.home.ai_provider.models import CoffeeUsage


class AIBaseClient:
    def test_connection(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        pass

    def list_models(self) -> List[Dict[str, str]]:
        pass

    def stream(self, model_name: str, user_input: str, system_prompt: str,
               on_usage_report: Optional[Callable[[CoffeeUsage], None]] = None, ) -> Iterable[str]:
        pass

    def generate(self, model_name: str, user_input: str, system_prompt: str) -> str:
        pass
