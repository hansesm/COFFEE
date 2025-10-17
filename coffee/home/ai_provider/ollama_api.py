import logging
from typing import Iterable, Optional, Tuple, List, Dict, Callable
from ollama import Client

from coffee.home.ai_provider.llm_provider_base import AIBaseClient
from coffee.home.ai_provider.configs import OllamaConfig
from coffee.home.ai_provider.models import OllamaUsage, CoffeeUsage

logger = logging.getLogger(__name__)

class OllamaClient(AIBaseClient):
    def __init__(
        self,
        config: Optional[OllamaConfig] = None,
    ) -> None:
        self.config = config
        if not self.config.host:
            raise ValueError("OLLAMA host ist nicht konfiguriert.")

        self._client: Optional[Client] = None

    # intern: Header bauen
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        return headers

    # intern: SDK-Client (lazy)
    def _client_obj(self) -> Client:
        if self._client is None:
            self._client = Client(
                host=self.config.host,
                verify=self.config.verify_ssl,
                headers=self._headers(),
                timeout=self.config.request_timeout,
            )
            logger.info(
                "Ollama Client instanziiert (host=%s, verify_ssl=%s, timeout=%ss)",
                self.config.host, self.config.verify_ssl, self.config.request_timeout
            )
        return self._client

    # --- Interface: Modelle aus Settings (wie bei Azure-Variante) ------------
    def list_models(self) -> List[Dict[str, str]]:
        models = [{"name": m, "backend": "ollama"} for m in (self.config.model_names or []) if m]
        logger.info("Konfigurierte Ollama-Modelle: %s", [m["name"] for m in models])
        return models

    # --- Interface: Health-Check ---------------------------------------------
    def test_connection(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Leichter Check: /api/tags via client.list() + optional Mini-Chat.
        """
        try:
            _ = self._client_obj().list()  # prüft Erreichbarkeit & Auth
            return True, "Verbindung ok."
        except Exception as e:
            logger.exception("Ollama list() fehlgeschlagen")
            return False, f"Verbindungsfehler: {e!s}"

    def stream(self, model_name: str, user_input: str, system_prompt: str,
               on_usage_report: Optional[Callable[[CoffeeUsage], None]] = None, ) -> Iterable[str]:
        """
        Streamt `message.content`-Deltas.
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_input})

            logger.info("Ollama Streaming gestartet (model=%s)", model_name)
            stream = self._client_obj().chat(
                model=model_name,
                messages=messages,
                stream=True,
                options={
                    # Annäherung an eure Defaults; bei Ollama heißen Params anders
                    "temperature": 0.8,
                    "top_p": 0.1,
                    # presence/frequency penalties werden nicht von allen Modellen unterstützt
                },
            )
            for chunk in stream:
                if chunk.get("message", {}).get("content"):
                    yield chunk["message"]["content"]

                if chunk.get("done"):
                    try:
                        usage = OllamaUsage.from_ollama_payload(chunk)
                        if on_usage_report:
                            on_usage_report(CoffeeUsage(tokens_used_system=usage.prompt_eval_count,
                                                        tokens_used_completion=usage.eval_count,
                                                        total_duration_ns=usage.total_duration_ns))

                        logger.info(
                            "Ollama Usage: prompt=%s, completion=%s, total=%sns",
                            usage.prompt_tokens, usage.completion_tokens, usage.total_duration_ns
                        )
                    except Exception:
                        logger.debug("Konnte Usage aus letztem Chunk nicht lesen", exc_info=True)
        except Exception as e:
            logger.exception("Ollama Streaming Fehler")
            yield f"Ollama streaming error: {e!s}"

    def generate(self, model_name: str, user_input: str, system_prompt: str) -> str:
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_input})

            logger.info("Ollama Generate gestartet (model=%s)", model_name)
            resp = self._client_obj().chat(
                model=model_name,
                messages=messages,
                stream=False,
                options={
                    "temperature": 0.8,
                    "top_p": 0.1,
                    # num_predict analog zu max_tokens; None = Modellstandard
                },
            )
            return (resp.get("message", {}).get("content") or "").strip()
        except Exception as e:
            logger.exception("Ollama Generate Fehler")
            return f"Ollama generation error: {e!s}"
