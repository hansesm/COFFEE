import time
from typing import Optional, Tuple, Callable, Generator
import logging

from openai import AzureOpenAI
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionChunk

from coffee.home.ai_provider.llm_provider_base import AIBaseClient
from coffee.home.ai_provider.models import CoffeeUsage
from coffee.home.ai_provider.token_estimator import RoughStrategy, TokenEstimatorStrategy

logger = logging.getLogger(__name__)


class AzureOpenAIClient(AIBaseClient):

    def __init__(
        self,
        config: "AzureOpenAIConfig",
        logger_: Optional[logging.Logger] = None,
        token_estimator: TokenEstimatorStrategy = RoughStrategy(),
    ) -> None:
        self.config = config
        self.logger = logger_ or logger
        if not self.config.endpoint:
            raise ValueError("AzureOpenAIClient: endpoint is required in configuration.")
        if not self.config.api_key:
            raise ValueError("AzureOpenAIClient: api_key is required in configuration.")
        self._client: Optional[AzureOpenAI] = None
        self._token_estimator = token_estimator

    def _client_obj(self) -> AzureOpenAI:
        if self._client is None:
            self._client = AzureOpenAI(
                api_version=self.config.api_version,
                azure_endpoint=self.config.endpoint,
                api_key=self.config.api_key,
                timeout=self.config.request_timeout,
                max_retries=self.config.max_retries
            )
            self.logger.info(
                "AzureOpenAI client initialized (endpoint=%s, api_version=%s)",
                self.config.endpoint, self.config.api_version
            )
        return self._client

    def test_connection(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Minimal health check: very short chat completion.
        """
        model = model_name or (
            self.config.default_model or (self.config.model_names[0] if self.config.model_names else None)
        )
        if not model:
            return False, "No deployment/model configured."

        try:
            resp = self._client_obj().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a health check. Reply with 'ok'."},
                    {"role": "user", "content": "ping"},
                ]
            )
            ok = bool(resp and resp.choices and getattr(resp.choices[0].message, "content", "").strip())
            return (True, "Connection OK.") if ok else (False, "Empty response received.")
        except Exception as e:
            msg = str(e)
            if "deploymentnotfound" in msg.lower():
                return False, f"Deployment '{model}' not found."
            self.logger.exception("AzureOpenAI health check failed")
            return False, f"Error during test: {e!s}"

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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        self.logger.info("AzureOpenAI streaming started (deployment=%s)", model_name)

        all_content = ""
        usage: Optional[CoffeeUsage] = None
        t0 = time.perf_counter_ns()

        try:
            response = self._client_obj().chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
                **llm_model.default_params,
                stream_options={"include_usage": True},
            )

            for chunk in response:
                try:
                    if chunk.usage:
                        usage = self._make_usage_from_openai(chunk.usage)

                    for piece in self._extract_contents(chunk):
                        if piece:
                            all_content += piece
                            yield piece

                except Exception:
                    self.logger.debug("Chunk could not be interpreted: %r", chunk, exc_info=True)
                    continue

        except Exception as e:
            msg = str(e)
            if "deploymentnotfound" in msg.lower() or ("deployment" in msg.lower() and "not exist" in msg.lower()):
                self.logger.error("Deployment not found: %s", model_name)
                yield f"Azure OpenAI deployment '{model_name}' not found. Please check configuration."
            else:
                self.logger.exception("AzureOpenAI streaming error")
                yield f"Azure OpenAI streaming error: {e!s}"

        finally:
            elapsed_ns = time.perf_counter_ns() - t0

            if usage is None:
                self.logger.info("No token usage reported by Azure. Estimating with '%s'.", self._token_estimator.name)
                usage = self._estimate_usage(system_prompt, user_input, all_content, elapsed_ns)

            if usage.total_duration_ns is None or usage.total_duration_ns == 0:
                usage.total_duration_ns = elapsed_ns

            if on_usage_report:
                try:
                    on_usage_report(usage)
                except Exception:
                    self.logger.exception("on_usage_report callback failed")

            self.logger.info("AzureOpenAI streaming finished (duration=%.3fs)", elapsed_ns / 1e9)

    def _extract_contents(self, chunk: ChatCompletionChunk) -> Generator[str, None, None]:
        """
        Extract text deltas from stream chunks.
        Expected schema (OpenAI/AzureOpenAI):
          - chunk.choices[0].delta.content (incremental)
        """
        choices = chunk.choices
        if not choices:
            return
        for ch in choices:
            delta = ch.delta
            if delta is not None:
                content = delta.content
                if content:
                    yield content

    def _make_usage_from_openai(self, openai_usage: CompletionUsage) -> CoffeeUsage:
        """
        Convert AzureOpenAI usage object to CoffeeUsage.
        """
        prompt_tokens = openai_usage.prompt_tokens or 0
        completion_tokens = openai_usage.completion_tokens or 0
        total_tokens = openai_usage.total_tokens or (prompt_tokens + completion_tokens)

        self.logger.info(
            "AzureOpenAI usage: prompt=%s, completion=%s, total=%s",
            prompt_tokens, completion_tokens, total_tokens
        )

        return CoffeeUsage(
            tokens_used_system=prompt_tokens,
            tokens_used_completion=completion_tokens
        )

    def _estimate_usage(self, system_prompt: str, user_input: str, completion_text: str, elapsed_ns: int) -> CoffeeUsage:
        """
        Fallback token estimation using the configured token estimator.
        """
        sys_tokens = self._token_estimator.estimate(system_prompt).tokens
        user_tokens = self._token_estimator.estimate(user_input).tokens
        completion_tokens = self._token_estimator.estimate(completion_text).tokens

        usage = CoffeeUsage(
            tokens_used_system=sys_tokens,
            tokens_used_user=user_tokens,
            tokens_used_completion=completion_tokens,
            total_duration_ns=elapsed_ns,
        )
        return usage
