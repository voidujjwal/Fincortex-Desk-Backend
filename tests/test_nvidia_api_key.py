import os
import unittest
from unittest.mock import patch

from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.openai_client import OpenAIClient


class TestNvidiaProvider(unittest.TestCase):
    """Verify NVIDIA provider initialization, base_url, API key handling, and model routing."""

    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_nvidia_client_creation(self, mock_chat):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-env-key-123"}):
            client = create_llm_client(
                provider="nvidia",
                model="nvidia/nemotron-3-super-120b-a12b",
                reasoning_budget=16384,
                chat_template_kwargs={"enable_thinking": True},
            )
            self.assertIsInstance(client, OpenAIClient)
            client.get_llm()

            call_kwargs = mock_chat.call_args[1]
            self.assertEqual(call_kwargs.get("base_url"), "https://integrate.api.nvidia.com/v1")
            self.assertEqual(call_kwargs.get("api_key"), "nvapi-env-key-123")
            self.assertEqual(call_kwargs.get("model"), "nvidia/nemotron-3-super-120b-a12b")
            
            extra_body = call_kwargs.get("extra_body", {})
            self.assertEqual(extra_body.get("reasoning_budget"), 16384)
            self.assertEqual(extra_body.get("chat_template_kwargs"), {"enable_thinking": True})

    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_nvidia_explicit_api_key_override(self, mock_chat):
        client = create_llm_client(
            provider="nvidia",
            model="nvidia/nemotron-3-super-120b-a12b",
            api_key="nvapi-explicit-key-456",
        )
        client.get_llm()
        call_kwargs = mock_chat.call_args[1]
        self.assertEqual(call_kwargs.get("api_key"), "nvapi-explicit-key-456")

    def test_provider_resolution(self):
        import sys
        sys.path.insert(0, "backend")
        from app.services.trading_agents_service import TradingAgentsService
        service = TradingAgentsService()

        self.assertEqual(service._resolve_provider("nvidia/nemotron-3-super-120b-a12b"), "nvidia")
        self.assertEqual(service._resolve_provider("gemini-3-flash-preview"), "google")
        self.assertEqual(service._resolve_provider("gemini-2.5-flash"), "google")
        self.assertEqual(service._resolve_provider("gpt-5.4"), "openai")
        self.assertEqual(service._resolve_provider("claude-sonnet-4-6"), "anthropic")
        self.assertEqual(service._resolve_provider("grok-4-1-fast-reasoning"), "xai")
        self.assertEqual(service._resolve_provider("z-ai/glm-4.5-air"), "openrouter")


if __name__ == "__main__":
    unittest.main()
