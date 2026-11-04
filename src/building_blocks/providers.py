"""Ollama and Anthropic adapters with one tiny provider-independent message format.

Message format: {role:'user'|'system'|'assistant'|'tool', content:str,
                 tool_calls:[{id,name,arguments}], tool_name:str}
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ProviderError(RuntimeError):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Any


@dataclass
class ModelResponse:
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    stop_reason: str = "end_turn"
    model: str = ""


class OllamaProvider:
    def __init__(self, model: str = "qwen2.5:7b", host: str = "http://localhost:11434",
                 temperature: float = 0.0):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature

    def _request(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = urllib.request.Request(
            self.host + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ProviderError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(f"Cannot reach Ollama at {self.host}: {exc}. "
                                "Start `ollama serve` and pull the selected model.") from exc

    @staticmethod
    def _ollama_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted = []
        for message in messages:
            role = message["role"]
            if role == "tool":
                converted.append({"role": "tool", "tool_name": message["tool_name"],
                                  "content": message["content"]})
                continue
            entry = {"role": role, "content": message.get("content", "")}
            if role == "assistant" and message.get("tool_calls"):
                entry["tool_calls"] = [{"type": "function", "function": {
                    "name": call["name"], "arguments": call["arguments"]}}
                    for call in message["tool_calls"]]
            converted.append(entry)
        return converted

    def generate(self, messages: List[Dict[str, Any]],
                 tools: Optional[List[Dict[str, Any]]] = None) -> ModelResponse:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._ollama_messages(messages),
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": 1024},
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": {
                "name": spec["name"], "description": spec["description"],
                "parameters": spec["input_schema"]}} for spec in tools]
        data = self._request("/api/chat", payload)
        msg = data.get("message", {})
        calls = []
        for raw in msg.get("tool_calls") or []:
            fn = raw.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_malformed_json": args[:100]}
            calls.append(ToolCall(str(raw.get("id") or f"ollama_{uuid.uuid4().hex[:12]}"),
                                  fn.get("name", ""), args))
        return ModelResponse(text=msg.get("content", "") or "", tool_calls=calls,
                             input_tokens=data.get("prompt_eval_count"),
                             output_tokens=data.get("eval_count"),
                             stop_reason="tool_use" if calls else "end_turn",
                             model=data.get("model", self.model))

    def check_connection(self) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=8) as response:
                data = json.load(response)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(f"Ollama is not running at {self.host}: {exc}") from exc
        models = [entry.get("name") for entry in data.get("models", [])]
        return {"server": self.host, "installed_models": models,
                "selected_model": self.model,
                "selected_model_installed": any(x == self.model or x.startswith(self.model + ":") for x in models)}


class AnthropicProvider:
    def __init__(self, model: str = "claude-sonnet-5"):
        try:
            import anthropic  # Installed only when the user chooses this backend.
        except ImportError as exc:
            raise ProviderError("Missing Anthropic SDK. Run `pip install -U anthropic`.") from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ProviderError("Set ANTHROPIC_API_KEY in your shell (do not commit it).")
        self.client = anthropic.Anthropic()
        self.model = model

    @staticmethod
    def _anthropic_messages(messages: List[Dict[str, Any]]) -> Any:
        output = []
        system_parts = []
        pending_tool_results = []

        def flush_tools():
            if pending_tool_results:
                output.append({"role": "user", "content": list(pending_tool_results)})
                pending_tool_results.clear()

        for m in messages:
            role = m["role"]
            if role == "system":
                flush_tools()
                system_parts.append(m.get("content", ""))
            elif role == "tool":
                pending_tool_results.append({"type": "tool_result",
                                             "tool_use_id": m["tool_call_id"],
                                             "content": m["content"],
                                             "is_error": m.get("is_error", False)})
            elif role == "assistant":
                flush_tools()
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for call in m.get("tool_calls", []):
                    blocks.append({"type": "tool_use", "id": call["id"],
                                   "name": call["name"], "input": call["arguments"]})
                output.append({"role": "assistant", "content": blocks})
            elif role == "user":
                flush_tools()
                output.append({"role": "user", "content": m["content"]})
        flush_tools()
        return "\n".join(system_parts), output

    def generate(self, messages: List[Dict[str, Any]],
                 tools: Optional[List[Dict[str, Any]]] = None) -> ModelResponse:
        system, converted = self._anthropic_messages(messages)
        kwargs: Dict[str, Any] = {"model": self.model, "max_tokens": 1024,
                                  "messages": converted}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        try:
            response = self.client.messages.create(**kwargs)
        except Exception as exc:
            raise ProviderError(f"Anthropic request failed: {exc}") from exc
        text_parts = []
        calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(block.id, block.name, block.input))
        return ModelResponse(text="\n".join(text_parts), tool_calls=calls,
                             input_tokens=getattr(response.usage, "input_tokens", None),
                             output_tokens=getattr(response.usage, "output_tokens", None),
                             stop_reason=response.stop_reason or "unknown", model=response.model)


def create_provider(name: str = "ollama", model: Optional[str] = None,
                    temperature: float = 0.0):
    if name == "ollama":
        return OllamaProvider(model=model or "qwen2.5:7b", temperature=temperature)
    if name == "anthropic":
        return AnthropicProvider(model=model or "claude-sonnet-5")
    raise ValueError("provider must be 'ollama' or 'anthropic'")
