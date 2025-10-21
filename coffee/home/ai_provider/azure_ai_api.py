import logging
import time
from typing import Optional, Tuple, List, Dict, Callable, Generator

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, StreamingChatCompletionsUpdate, CompletionsUsage
from azure.core.credentials import AzureKeyCredential

from coffee.home.ai_provider.configs import AzureAIConfig
from coffee.home.ai_provider.llm_provider_base import AIBaseClient
from coffee.home.ai_provider.models import CoffeeUsage
from coffee.home.ai_provider.token_estimator import RoughStrategy, TokenEstimatorStrategy

logger = logging.getLogger(__name__)


class AzureAIClient(AIBaseClient):
    """
    Implementiert AIBaseClient für Azure AI Inference auf Basis einer AzureAIConfig.
    """

    def __init__(self, config: AzureAIConfig, logger_: Optional[logging.Logger] = None,
                 token_estimator: TokenEstimatorStrategy = RoughStrategy()) -> None:
        self.config = config
        self.logger = logger_ or logger
        if not self.config.endpoint or not self.config.api_key:
            raise ValueError("AzureAIClient: endpoint oder api_key fehlen in AzureAIConfig.")
        self._client: Optional[ChatCompletionsClient] = None
        self._token_estimator = token_estimator

    def _client_obj(self) -> ChatCompletionsClient:
        if self._client is None:
            self._client = ChatCompletionsClient(
                endpoint=self.config.endpoint,
                credential=AzureKeyCredential(self.config.api_key),
                api_version=self.config.api_version,
                frequency_penalty=self.config.frequency_penalty,
                presence_penalty=self.config.presence_penalty,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                max_tokens=self.config.max_tokens
            )
            self.logger.info(
                "Azure AI Client initialisiert (endpoint=%s, api_version=%s)",
                self.config.endpoint, self.config.api_version
            )
        return self._client

    def test_connection(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Minimaler Health-Check: kurze Completion mit max_tokens=1.
        """
        model = model_name or (
                    self.config.default_model or (self.config.model_names[0] if self.config.model_names else None))
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
            ok = bool(
                resp and resp.choices and resp.choices[0].message and (resp.choices[0].message.content or "").strip())
            return (True, "Verbindung ok.") if ok else (False, "Leere Antwort erhalten.")
        except Exception as e:
            self.logger.exception("Azure AI Health-Check fehlgeschlagen")
            return False, f"Fehler beim Test: {e!s}"

    def stream(
        self,
        llm_model: "LLMModel",
        user_input: str,
        system_prompt: str,
        on_usage_report: Optional[Callable[[CoffeeUsage], None]] = None,
    ) -> Generator[str, None, None]:
        """
        Streaming completion. Yields incremental text chunks (str).
        Always reports usage (real or estimated) at the end.
        """
        model_name = llm_model.external_name
        messages = [SystemMessage(content=system_prompt), UserMessage(content=user_input)]
        self.logger.info("Azure streaming started (model=%s)", model_name)

        all_content = ""
        usage: Optional[CoffeeUsage] = None
        t0 = time.perf_counter_ns()

        try:
            response = self._client_obj().complete(
                messages=messages,
                model=model_name,
                **llm_model.default_params,
                stream=True,
            )

            for update in response:
                try:
                    if update.usage is not None:
                        self.logger.debug("Process usage report from Azure.")
                        usage = self._make_usage_from_azure(update.usage)

                    for piece in self._extract_contents(update):
                        if piece:
                            all_content += piece
                            yield piece

                except Exception:
                    self.logger.debug(
                        "Chunk could not be interpreted: %r",
                        update,
                        exc_info=True,
                    )
                    continue

        except Exception as e:
            # Errors creating the stream or iterating response -> user-facing message
            self.logger.exception("Azure AI streaming error")
            yield f"Azure AI streaming error: {e!s}"

        finally:
            elapsed_ns = time.perf_counter_ns() - t0

            if usage is None:
                self.logger.info(f"No token usage reported. Estimating with '{self._token_estimator.name}'.")
                usage = self._estimate_usage(system_prompt, user_input, all_content, elapsed_ns)

            if usage.total_duration_ns is None or usage.total_duration_ns == 0:
                usage.total_duration_ns = elapsed_ns

            if on_usage_report:
                try:
                    on_usage_report(usage)
                except Exception:
                    self.logger.exception("on_usage_report callback failed")

            self.logger.info("Azure streaming finished (duration=%.3fs)", elapsed_ns / 1e9)

    def _extract_contents(self, update: StreamingChatCompletionsUpdate) -> Generator[str, None]:
        """
        Extract text deltas from various update shapes.
        - Typical: update.choices[0].delta.content
        - Robust: iterate all choices; some SDKs expose `message` instead of `delta`.
        """
        choices = update.choices
        if not choices:
            return None

        for ch in choices:
            if ch.delta:
                yield ch.delta.content

        return None

    def _make_usage_from_azure(self, azure_usage: CompletionsUsage) -> CoffeeUsage:
        """
        Build a CoffeeUsage object from Azure usage; default missing fields to 0.
        No prints, structured logging only.
        """
        prompt_tokens = azure_usage.prompt_tokens or 0
        completion_tokens = azure_usage.completion_tokens or 0
        total_tokens = azure_usage.total_tokens or (prompt_tokens + completion_tokens)

        self.logger.info(
            "Azure Usage: prompt=%s, completion=%s, total=%s",
            prompt_tokens, completion_tokens, total_tokens
        )

        coffee_usage = CoffeeUsage(
            tokens_used_system=prompt_tokens,
            tokens_used_completion=completion_tokens
        )

        return coffee_usage

    def _estimate_usage(self, system_prompt: str, user_input: str, completion_text: str, elapsed_ns: int) -> CoffeeUsage:
        """
        Fallback estimation using the configured token estimator.
        """
        sys_tokens = self._token_estimator.estimate(system_prompt).tokens
        user_tokens = self._token_estimator.estimate(user_input).tokens
        out_tokens = self._token_estimator.estimate(completion_text).tokens

        usage = CoffeeUsage(
            tokens_used_system=sys_tokens,
            tokens_used_user=user_tokens,
            tokens_used_completion=out_tokens,
            total_duration_ns=elapsed_ns,
        )

        return usage
