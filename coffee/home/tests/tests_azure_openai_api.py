from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from coffee.home.ai_provider.azure_openai_api import AzureOpenAIClient
from coffee.home.ai_provider.configs import AzureOpenAIConfig
from coffee.home.ai_provider.token_estimator import TokenEstimate


class _StubCompletionUsage:
    def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _StubChoice:
    def __init__(self, content: str):
        self.delta = SimpleNamespace(content=content)


class _StubChunk:
    def __init__(self, contents=None, usage=None):
        self.choices = contents or []
        self.usage = usage


class _StubEstimator:
    def __init__(self):
        self.calls = []

    @property
    def name(self):
        return "stub"

    def estimate(self, text: str, **kwargs):
        self.calls.append(text)
        return TokenEstimate(tokens=len(text))


class AzureOpenAIClientTests(SimpleTestCase):
    def _config(self, **overrides):
        data = {
            "endpoint": "https://example.openai.azure.com",
            "api_key": "secret",
            "default_model": "demo",
        }
        data.update(overrides)
        return AzureOpenAIConfig(**data)

    def test_init_requires_endpoint(self):
        cfg = self._config(endpoint=None)
        with self.assertRaisesRegex(ValueError, "AzureOpenAIClient: endpoint is required in configuration."):
            AzureOpenAIClient(cfg)

    def test_init_requires_api_key(self):
        cfg = self._config(api_key=None)
        with self.assertRaisesRegex(ValueError, "AzureOpenAIClient: api_key is required in configuration."):
            AzureOpenAIClient(cfg)

    def test_client_obj_initializes_once(self):
        cfg = self._config()
        client = AzureOpenAIClient(cfg)
        with patch("coffee.home.ai_provider.azure_openai_api.AzureOpenAI") as mock_cls:
            mock_instance = mock_cls.return_value
            client_obj1 = client._client_obj()
            client_obj2 = client._client_obj()

        self.assertIs(client_obj1, mock_instance)
        self.assertIs(client_obj2, mock_instance)
        mock_cls.assert_called_once_with(
            api_version=cfg.api_version,
            azure_endpoint=cfg.endpoint,
            api_key=cfg.api_key,
            timeout=cfg.request_timeout,
            max_retries=cfg.max_retries,
        )

    def test_stream_yields_chunks_and_reports_usage(self):
        cfg = self._config()
        client = AzureOpenAIClient(cfg)

        usage = _StubCompletionUsage(prompt_tokens=4, completion_tokens=6, total_tokens=10)
        chunks = [
            _StubChunk(contents=[_StubChoice("hello ")]),
            _StubChunk(contents=[_StubChoice("world")], usage=usage),
        ]

        stub_client = MagicMock()
        stub_client.chat.completions.create.return_value = iter(chunks)
        with patch.object(client, "_client_obj", return_value=stub_client):
            llm_model = SimpleNamespace(external_name="demo", default_params={"temperature": 0.2})
            reported = []
            tokens = list(
                client.stream(
                    llm_model,
                    user_input="User",
                    system_prompt="System",
                    on_usage_report=reported.append,
                )
            )

        self.assertEqual("".join(tokens), "hello world")
        self.assertEqual(len(reported), 1)
        usage_report = reported[0]
        self.assertEqual(usage_report.tokens_used_system, 4)
        self.assertEqual(usage_report.tokens_used_completion, 6)

    def test_stream_estimates_when_usage_missing(self):
        cfg = self._config()
        estimator = _StubEstimator()
        client = AzureOpenAIClient(cfg, token_estimator=estimator)

        chunks = [
            _StubChunk(contents=[_StubChoice("result")], usage=None),
        ]

        stub_client = MagicMock()
        stub_client.chat.completions.create.return_value = iter(chunks)

        with patch.object(client, "_client_obj", return_value=stub_client), \
                patch("coffee.home.ai_provider.azure_openai_api.time.perf_counter_ns", side_effect=[50, 150]):
            llm_model = SimpleNamespace(external_name="demo", default_params={})
            reported = []
            parts = list(
                client.stream(
                    llm_model,
                    user_input="user",
                    system_prompt="sys",
                    on_usage_report=reported.append,
                )
            )

        self.assertEqual(parts, ["result"])
        self.assertEqual(len(reported), 1)
        usage = reported[0]
        self.assertEqual(usage.tokens_used_system, len("sys"))
        self.assertEqual(usage.tokens_used_user, len("user"))
        self.assertEqual(usage.tokens_used_completion, len("result"))
        self.assertEqual(usage.total_duration_ns, 100)
