import unittest
from src.building_blocks.providers import OllamaProvider, AnthropicProvider, ProviderError


class Providers(unittest.TestCase):
    def test_tool_translation(self):
        p = OllamaProvider(model="qwen2.5:3b")
        out = p._ollama_messages([{"role": "assistant", "content": "", "tool_calls":
                                   [{"name": "find_person", "id": "x", "arguments": {"query": "ana"}}]}])
        self.assertEqual(out[0]["tool_calls"][0]["function"]["name"], "find_person")

    def test_anthropic_tool_grouping(self):
        sys, msgs = AnthropicProvider._anthropic_messages([
            {"role": "system", "content": "demo"},
            {"role": "user", "content": "schedule"},
            {"role": "assistant", "content": "", "tool_calls":
             [{"name": "find_person", "id": "x", "arguments": {"query": "ana"}}]},
            {"role": "tool", "tool_call_id": "x", "tool_name": "find_person", "content": "{}"},
        ])
        self.assertEqual(sys, "demo")
        self.assertEqual(msgs[-1]["role"], "user")
        self.assertEqual(msgs[-1]["content"][0]["type"], "tool_result")


if __name__ == "__main__":
    unittest.main()
