from django.test import SimpleTestCase
from django.utils import translation

from coffee.home.ai_provider.token_estimator import RoughStrategy


class RoughStrategyTests(SimpleTestCase):
    def test_name_property(self):
        with translation.override("en"):
            strategy = RoughStrategy()
        self.assertEqual(strategy.name, "rough")

    def test_estimate_uses_language_baseline_de(self):
        text = "x" * 36  # 36 characters / 3.6 chars_per_token => ceil(10) tokens
        with translation.override("de"):
            strategy = RoughStrategy()
            estimate = strategy.estimate(text)

        self.assertEqual(estimate.tokens, 10)

    def test_estimate_falls_back_for_unknown_language(self):
        text = "x" * 18
        with translation.override("fr"):
            strategy = RoughStrategy()
            estimate = strategy.estimate(text)

        # falls back to default baseline 3.6 chars/token => ceil(5)
        self.assertEqual(estimate.tokens, 5)

    def test_chars_per_token_override(self):
        text = "x" * 50
        with translation.override("en"):
            strategy = RoughStrategy(chars_per_token=10)
            estimate = strategy.estimate(text)

        self.assertEqual(estimate.tokens, 5)
