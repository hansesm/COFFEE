from typing import Optional, Tuple, List, Dict, Iterable
import logging

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

from coffee.home.ai_provider.configs import AzureAIConfig
from coffee.home.ai_provider.llm_provider_base import AIBaseClient

logger = logging.getLogger(__name__)

class AzureAIClient(AIBaseClient):
    """
    Implementiert AIBaseClient für Azure AI Inference auf Basis einer AzureAIConfig.
    """

    def __init__(self, config: AzureAIConfig, logger_: Optional[logging.Logger] = None) -> None:
        self.config = config
        self.logger = logger_ or logger
        if not self.config.endpoint or not self.config.api_key:
            raise ValueError("AzureAIClient: endpoint oder api_key fehlen in AzureAIConfig.")
        self._client: Optional[ChatCompletionsClient] = None

    # Optionaler Convenience-Konstruktor – nur nutzen, wenn du Provider-ORM hast:
    @classmethod
    def from_provider(cls, provider: "Provider") -> "AzureAIClient":
        cfg = AzureAIConfig.from_provider(provider)
        return cls(cfg)

    # ---------- Intern ----------
    def _client_obj(self) -> ChatCompletionsClient:
        if self._client is None:
            self._client = ChatCompletionsClient(
                endpoint=self.config.endpoint,
                credential=AzureKeyCredential(self.config.api_key),
                api_version=self.config.api_version,
            )
            self.logger.info(
                "Azure AI Client initialisiert (endpoint=%s, api_version=%s)",
                self.config.endpoint, self.config.api_version
            )
        return self._client

    # ---------- AIBaseClient: Interface ----------
    def test_connection(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Minimaler Health-Check: kurze Completion mit max_tokens=1.
        """
        model = model_name or (self.config.default_model or (self.config.model_names[0] if self.config.model_names else None))
        if not model:
            return False, "Kein Modell konfiguriert."

        try:
            messages = [
                SystemMessage(content="You are a health check. Reply with 'ok'."),
                UserMessage(content="ping"),
            ]
            resp = self._client_obj().complete(
                messages=messages,
                model=model,
                max_tokens=1,
                temperature=0.0,
                top_p=1.0,
            )
            ok = bool(resp and resp.choices and resp.choices[0].message and (resp.choices[0].message.content or "").strip())
            return (True, "Verbindung ok.") if ok else (False, "Leere Antwort erhalten.")
        except Exception as e:
            self.logger.exception("Azure AI Health-Check fehlgeschlagen")
            return False, f"Fehler beim Test: {e!s}"

    def list_models(self) -> List[Dict[str, str]]:
        """
        Modelle aus der Config (schnell + deterministisch).
        """
        names = self.config.model_names or ([self.config.default_model] if self.config.default_model else [])
        models = [{"name": n, "backend": "azure_ai"} for n in names if n]
        self.logger.info("Konfigurierte Azure-Modelle: %s", [m["name"] for m in models])
        return models

    def stream(self, model_name: str, user_input: str, system_prompt: str) -> Iterable[str]:
        """
        Streaming-Completion. Gibt inkrementelle Textstücke (str) aus.
        """
        try:
            messages = [SystemMessage(content=system_prompt), UserMessage(content=user_input)]
            self.logger.info("Azure Streaming gestartet (model=%s)", model_name)
            response = self._client_obj().complete(
                messages=messages,
                model=model_name,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                presence_penalty=self.config.presence_penalty,
                frequency_penalty=self.config.frequency_penalty,
                stream=True,
            )
            for chunk in response:
                try:
                    if getattr(chunk, "choices", None):
                        choice = chunk.choices[0]
                        delta = getattr(choice, "delta", None)
                        content = getattr(delta, "content", None)
                        if content:
                            yield content
                    else:
                        self.logger.debug("Leerer Chunk: %r", chunk)
                except Exception:
                    self.logger.debug("Chunk konnte nicht interpretiert werden: %r", chunk, exc_info=True)
                    continue
        except Exception as e:
            self.logger.exception("Azure AI Streaming Fehler")
            yield f"Azure AI streaming error: {e!s}"

    def generate(self, model_name: str, user_input: str, system_prompt: str) -> str:
        """
        Non-Streaming-Completion. Gibt den gesamten Text zurück.
        """
        try:
            messages = [SystemMessage(content=system_prompt), UserMessage(content=user_input)]
            self.logger.info("Azure Generate gestartet (model=%s)", model_name)
            resp = self._client_obj().complete(
                messages=messages,
                model=model_name,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                presence_penalty=self.config.presence_penalty,
                frequency_penalty=self.config.frequency_penalty,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            self.logger.exception("Azure AI Generation Fehler")
            return f"Azure AI generation error: {e!s}"
