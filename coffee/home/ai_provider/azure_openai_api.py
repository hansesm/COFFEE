from typing import Optional, Tuple, List, Dict, Iterable, Any
import logging

from openai import AzureOpenAI

from coffee.home.ai_provider.llm_provider_base import AIBaseClient

logger = logging.getLogger(__name__)


class AzureOpenAIClient(AIBaseClient):
    """
    Azure OpenAI Client auf Basis einer AzureOpenAIConfig.
    Implementiert: test_connection, list_models, stream, generate.
    """

    def __init__(self, config: "AzureOpenAIConfig", logger_: Optional[logging.Logger] = None) -> None:
        self.config = config
        self.logger = logger_ or logger
        if not self.config.endpoint or not self.config.api_key:
            raise ValueError("AzureOpenAIClient: endpoint oder api_key fehlen in der Config.")
        self._client: Optional[AzureOpenAI] = None

    @classmethod
    def from_provider(cls, provider: "Provider") -> "AzureOpenAIClient":
        cfg = AzureOpenAIConfig.from_provider(provider)
        return cls(cfg)

    # ---- intern -------------------------------------------------------------
    def _client_obj(self) -> AzureOpenAI:
        if self._client is None:
            self._client = AzureOpenAI(
                api_version=self.config.api_version,
                azure_endpoint=self.config.endpoint,
                api_key=self.config.api_key,
            )
            self.logger.info("AzureOpenAI Client initialisiert (endpoint=%s, api_version=%s)",
                             self.config.endpoint, self.config.api_version)
        return self._client

    # ---- AIBaseClient -------------------------------------------------------
    def test_connection(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Minimaler Health-Check: kurze Chat-Completion mit max_tokens=1.
        """
        model = model_name or (self.config.default_model or (self.config.model_names[0] if self.config.model_names else None))
        if not model:
            return False, "Kein Deployment/Modell konfiguriert."

        try:
            resp = self._client_obj().chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                timeout=self.config.request_timeout,
                temperature=0.0,
            )
            ok = bool(resp and resp.choices and getattr(resp.choices[0].message, "content", "").strip())
            return (True, "Verbindung ok.") if ok else (False, "Leere Antwort erhalten.")
        except Exception as e:
            msg = str(e)
            if "deploymentnotfound" in msg.lower():
                return False, f"Deployment '{model}' nicht gefunden."
            self.logger.exception("AzureOpenAI Health-Check fehlgeschlagen")
            return False, f"Fehler beim Test: {e!s}"

    def list_models(self) -> List[Dict[str, str]]:
        names = self.config.model_names or ([self.config.default_model] if self.config.default_model else [])
        models = [{"name": n, "backend": "azure_openai"} for n in names if n]
        self.logger.info("Konfigurierte Azure OpenAI Deployments: %s", [m["name"] for m in models])
        return models

    def stream(self, model_name: str, user_input: str, system_prompt: str) -> Iterable[str]:
        """
        Streamt Antwort-Tokens. Gibt Text-Teilstücke (str) aus.
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
            self.logger.info("AzureOpenAI Streaming gestartet (deployment=%s)", model_name)
            stream = self._client_obj().chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                timeout=self.config.request_timeout,
            )
            for chunk in stream:
                try:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = getattr(chunk.choices[0], "delta", None)
                        content = getattr(delta, "content", None) if delta else None
                        if content:
                            yield content
                    else:
                        self.logger.debug("Leerer Chunk: %r", chunk)
                except Exception:
                    self.logger.debug("Chunk konnte nicht interpretiert werden: %r", chunk, exc_info=True)
                    continue
        except Exception as e:
            msg = str(e)
            if "deploymentnotfound" in msg.lower() or ("deployment" in msg.lower() and "not exist" in msg.lower()):
                self.logger.error("Deployment nicht gefunden: %s", model_name)
                yield f"Azure OpenAI deployment '{model_name}' not found. Bitte Konfiguration prüfen."
            else:
                self.logger.exception("AzureOpenAI Streaming Fehler")
                yield f"Azure OpenAI streaming error: {e!s}"

    def generate(self, model_name: str, user_input: str, system_prompt: str) -> str:
        """
        Nicht-streamende Completion, gibt den kompletten Text zurück.
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
            self.logger.info("AzureOpenAI Generate gestartet (deployment=%s)", model_name)
            resp = self._client_obj().chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                timeout=self.config.request_timeout,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            msg = str(e)
            if "deploymentnotfound" in msg.lower() or ("deployment" in msg.lower() and "not exist" in msg.lower()):
                self.logger.error("Deployment nicht gefunden: %s", model_name)
                return f"Azure OpenAI deployment '{model_name}' not found. Bitte Konfiguration prüfen."
            self.logger.exception("AzureOpenAI Generation Fehler")
            return f"Azure OpenAI generation error: {e!s}"
