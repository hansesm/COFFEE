from types import SimpleNamespace
from unittest.mock import MagicMock, patch, ANY

from django.test import SimpleTestCase

from coffee.home.ai_provider.azure_ai_api import AzureAIClient
from coffee.home.ai_provider.configs import AzureAIConfig
from coffee.home.ai_provider.token_estimator import TokenEstimate


class _StubChatCompletionsClient:
    def __init__(self, *args, **kwargs):
        pass

    def complete(self, *args, **kwargs):
        return []


class _StubMessage:
    def __init__(self, content: str):
        self.content = content


class _StubUsage:
    def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _StubUpdate:
    def __init__(self, pieces=None, usage=None):
        self.choices = pieces or []
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


class AzureAIClientTests(SimpleTestCase):
    def _config(self, **overrides):
        data = {
            "endpoint": "https://example.azure.com",
            "api_key": "secret",
            "deployment": "demo",
            "default_model": "demo",
            "model_names": ["demo"],
        }
        data.update(overrides)
        return AzureAIConfig(**data)

    def test_init_requires_credentials(self):
        cfg = self._config(api_key=None)
        with self.assertRaises(ValueError):
            AzureAIClient(cfg)

    def test_client_obj_initializes_once(self):
        cfg = self._config()
        client = AzureAIClient(cfg)
        with patch("coffee.home.ai_provider.azure_ai_api.ChatCompletionsClient") as mock_cls, \
                patch("coffee.home.ai_provider.azure_ai_api.AzureKeyCredential") as mock_cred:
            mock_instance = mock_cls.return_value
            result1 = client._client_obj()
            result2 = client._client_obj()

        self.assertIs(result1, mock_instance)
        self.assertIs(result2, mock_instance)
        mock_cred.assert_called_once_with(cfg.api_key)
        mock_cls.assert_called_once_with(
            endpoint=cfg.endpoint,
            credential=ANY,
            api_version=cfg.api_version,
            frequency_penalty=cfg.frequency_penalty,
            presence_penalty=cfg.presence_penalty,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_tokens=cfg.max_tokens,
        )

    def test_stream_yields_chunks_and_reports_usage(self):
        cfg = self._config()
        client = AzureAIClient(cfg)
        fake_usage = _StubUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5)
        delta1 = SimpleNamespace(delta=SimpleNamespace(content="Hello "))
        delta2 = SimpleNamespace(delta=SimpleNamespace(content="World"))
        updates = [
            _StubUpdate([delta1], usage=None),
            _StubUpdate([delta2], usage=fake_usage),
        ]

        stub_client = MagicMock()
        stub_client.complete.return_value = iter(updates)

        with patch.object(client, "_client_obj", return_value=stub_client):
            llm_model = SimpleNamespace(external_name="demo", default_params={"temperature": 0.1})
            reported = []

            chunks = list(
                client.stream(
                    llm_model,
                    user_input="Hi",
                    system_prompt="System prompt",
                    on_usage_report=reported.append,
                )
            )

        self.assertEqual("".join(chunks), "Hello World")
        self.assertEqual(len(reported), 1)
        usage = reported[0]
        self.assertEqual(usage.tokens_used_system, 2)
        self.assertEqual(usage.tokens_used_completion, 3)

    def test_stream_estimates_when_usage_missing(self):
        cfg = self._config()
        estimator = _StubEstimator()
        client = AzureAIClient(cfg, token_estimator=estimator)
        delta = SimpleNamespace(delta=SimpleNamespace(content="out"))
        updates = [_StubUpdate([delta], usage=None)]
        stub_client = MagicMock()
        stub_client.complete.return_value = iter(updates)

        with patch.object(client, "_client_obj", return_value=stub_client), \
                patch("coffee.home.ai_provider.azure_ai_api.time.perf_counter_ns", side_effect=[100, 300]):
            llm_model = SimpleNamespace(external_name="demo", default_params={})
            reported = []
            chunks = list(
                client.stream(
                    llm_model,
                    user_input="user",
                    system_prompt="sys",
                    on_usage_report=reported.append,
                )
            )

        self.assertEqual(chunks, ["out"])
        self.assertEqual(len(reported), 1)
        usage = reported[0]
        self.assertEqual(usage.tokens_used_system, len("sys"))
        self.assertEqual(usage.tokens_used_user, len("user"))
        self.assertEqual(usage.tokens_used_completion, len("out"))
        self.assertEqual(usage.total_duration_ns, 200)
