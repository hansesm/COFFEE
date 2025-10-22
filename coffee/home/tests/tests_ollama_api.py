from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from coffee.home.ai_provider.configs import OllamaConfig
from coffee.home.ai_provider.ollama_api import OllamaClient


class OllamaClientTests(SimpleTestCase):
    def _config(self, **overrides):
        data = {
            "host": "http://localhost:11434",
            "verify_ssl": True,
            "auth_token": None,
            "default_model": "phi",
        }
        data.update(overrides)
        return OllamaConfig(**data)

    def test_init_requires_host(self):
        cfg = self._config(host="")
        with self.assertRaises(ValueError):
            OllamaClient(cfg)

    def test_headers_include_auth_when_token_present(self):
        cfg = self._config(auth_token="token")
        client = OllamaClient(cfg)
        self.assertEqual(
            client._headers(),
            {"Content-Type": "application/json", "Authorization": "Bearer token"},
        )

    def test_client_obj_initializes_once(self):
        cfg = self._config()
        client = OllamaClient(cfg)
        with patch("coffee.home.ai_provider.ollama_api.Client") as mock_cls:
            mock_instance = mock_cls.return_value
            obj1 = client._client_obj()
            obj2 = client._client_obj()

        self.assertIs(obj1, mock_instance)
        self.assertIs(obj2, mock_instance)
        mock_cls.assert_called_once_with(
            host=cfg.host,
            verify=cfg.verify_ssl,
            headers={"Content-Type": "application/json"},
            timeout=cfg.request_timeout,
        )

    def test_stream_yields_chunks_and_reports_usage(self):
        cfg = self._config()
        client = OllamaClient(cfg)

        stream_sequence = [
            {"message": {"content": "hello "}},
            {"message": {"content": "world"}, "done": True, "prompt_eval_count": 2, "eval_count": 3,
             "total_duration": 5, "prompt_eval_duration": 1},
        ]

        stub_client = MagicMock()
        stub_client.chat.return_value = iter(stream_sequence)

        with patch.object(client, "_client_obj", return_value=stub_client):
            llm_model = SimpleNamespace(external_name="phi", default_params={"temperature": 0.4})
            reported = []
            chunks = list(
                client.stream(
                    llm_model,
                    user_input="User prompt",
                    system_prompt="System prompt",
                    on_usage_report=reported.append,
                )
            )

        self.assertEqual("".join(chunks), "hello world")
        self.assertEqual(len(reported), 1)
        usage = reported[0]
        self.assertEqual(usage.tokens_used_system, 2)
        self.assertEqual(usage.tokens_used_completion, 3)

    def test_stream_handles_errors(self):
        cfg = self._config()
        client = OllamaClient(cfg)
        stub_client = MagicMock()
        stub_client.chat.side_effect = RuntimeError("boom")

        with patch.object(client, "_client_obj", return_value=stub_client):
            llm_model = SimpleNamespace(external_name="phi", default_params={})
            chunks = list(
                client.stream(
                    llm_model,
                    user_input="text",
                    system_prompt="sys",
                    on_usage_report=None,
                )
            )

        self.assertTrue(chunks)
        self.assertIn("Ollama streaming error", chunks[0])
