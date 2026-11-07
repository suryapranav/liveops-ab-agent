"""Talking to the language model.

Everything model-specific lives here behind one method, chat(). The agent
loop doesn't know whether it is talking to Ollama, a hosted API, or the
scripted fake used in tests, so swapping models is a one-line change.

OllamaClient uses only the standard library (urllib) to POST to Ollama's
/api/chat endpoint, so there is no SDK hiding what is sent.
"""
import json
import urllib.request
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class ChatResponse:
    content: str                   # the model's text (may be empty when it calls tools)
    tool_calls: list               # list[ToolCall]
    input_tokens: int
    output_tokens: int
    message: dict                  # the assistant message, to append to the history as-is
    server_timings_ms: dict = field(default_factory=dict)  # Ollama's own timings, if any


# Ollama reports these in nanoseconds. load_duration is model loading: large
# on a cold start, which explains a slow first call in a trace.
_OLLAMA_TIMINGS = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")


def parse_ollama_response(data):
    """Turn Ollama's /api/chat JSON into a ChatResponse."""
    message = data["message"]
    calls = []
    for call in message.get("tool_calls") or []:
        arguments = call["function"].get("arguments") or {}
        if isinstance(arguments, str):  # some models return arguments as a JSON string
            arguments = json.loads(arguments)
        calls.append(ToolCall(name=call["function"]["name"], arguments=arguments))
    return ChatResponse(
        content=message.get("content") or "",
        tool_calls=calls,
        input_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        message=message,
        server_timings_ms={k: round(data[k] / 1e6, 1) for k in _OLLAMA_TIMINGS if k in data},
    )


class OllamaClient:
    def __init__(self, model="qwen3.5:4b", host="http://localhost:11434",
                 temperature=0.0, seed=0, timeout_s=300):
        self.model = model
        self.host = host.rstrip("/")
        # temperature 0 + fixed seed: as repeatable as the model allows,
        # which matters for evals (same question -> same answer).
        self.options = {"temperature": temperature, "seed": seed}
        self.timeout_s = timeout_s

    def chat(self, messages, tools=None, response_format=None):
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # Qwen3.5 "thinks" by default; thinking can swallow tool calls
            # into the reasoning text, so we turn it off.
            "think": False,
            "options": self.options,
        }
        if tools:
            body["tools"] = tools
        if response_format:
            # A JSON schema: Ollama constrains generation to match it.
            body["format"] = response_format
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            return parse_ollama_response(json.load(response))


@dataclass
class ScriptedClient:
    """A fake model for tests: returns pre-written responses in order and
    records every request, so tests can check exactly what the loop sent."""
    responses: list
    requests: list = field(default_factory=list)

    def chat(self, messages, tools=None, response_format=None):
        # Copy the message list: the loop keeps appending to the same list.
        self.requests.append({"messages": list(messages), "tools": tools,
                              "response_format": response_format})
        if not self.responses:
            raise RuntimeError("ScriptedClient ran out of responses")
        return self.responses.pop(0)


def scripted_tool_call(name, arguments=None, tokens=(10, 5)):
    """Build a fake response in which the model calls one tool."""
    arguments = arguments or {}
    message = {"role": "assistant", "content": "",
               "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}
    return ChatResponse("", [ToolCall(name, arguments)], tokens[0], tokens[1], message)


def scripted_text(content, tokens=(10, 5)):
    """Build a fake response in which the model just replies with text."""
    return ChatResponse(content, [], tokens[0], tokens[1],
                        {"role": "assistant", "content": content})
