"""Check OllamaClient's real HTTP code against a tiny fake Ollama server.

This verifies the request we send (endpoint, model, think=False, tools,
format, options) without needing Ollama or a model installed.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from liveops_agent import OllamaClient

CANNED = {
    "message": {"role": "assistant", "content": "",
                "tool_calls": [{"function": {"name": "sample_ratio_check", "arguments": {}}}]},
    "prompt_eval_count": 50, "eval_count": 7,
}


@pytest.fixture
def fake_ollama():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append({"path": self.path, "body": json.loads(body)})
            payload = json.dumps(CANNED).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):  # keep test output quiet
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)  # port 0 = any free port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", received
    server.shutdown()


def test_request_and_response(fake_ollama):
    host, received = fake_ollama
    client = OllamaClient(model="qwen3.5:4b", host=host)
    tools = [{"type": "function", "function": {"name": "t", "parameters": {}}}]
    r = client.chat([{"role": "user", "content": "hi"}], tools=tools)

    sent = received[0]
    assert sent["path"] == "/api/chat"
    assert sent["body"]["model"] == "qwen3.5:4b"
    assert sent["body"]["think"] is False and sent["body"]["stream"] is False
    assert sent["body"]["options"] == {"temperature": 0.0, "seed": 0}
    assert sent["body"]["tools"] == tools and "format" not in sent["body"]
    assert r.tool_calls[0].name == "sample_ratio_check"
    assert (r.input_tokens, r.output_tokens) == (50, 7)


def test_format_is_sent_for_memo(fake_ollama):
    host, received = fake_ollama
    schema = {"type": "object"}
    OllamaClient(host=host).chat([{"role": "user", "content": "hi"}], response_format=schema)
    assert received[0]["body"]["format"] == schema and "tools" not in received[0]["body"]
