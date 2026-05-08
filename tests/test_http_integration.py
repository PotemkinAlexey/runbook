import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from runbook import Runbook, equals, step
from runbook.integrations.http import get_json, get_text, post_json


class HttpIntegrationTest(unittest.TestCase):
    def test_get_text_and_json_loaders(self):
        with TestHttpServer() as server:
            context = {"base_url": server.url}

            Runbook("http").add(
                step("GET")
                .load("text", get_text("{{ base_url }}/text"))
                .load("payload", get_json("{{ base_url }}/json"))
                .require(equals("payload.ok", True))
            ).run(context)

            self.assertEqual(context["text"], "hello")
            self.assertEqual(context["payload"], {"ok": True})

    def test_post_json_action(self):
        with TestHttpServer() as server:
            context = {"base_url": server.url, "payload": {"ok": True}}

            step("POST").then(post_json("{{ base_url }}/post", "payload")).run(context)

            self.assertEqual(server.received_payload, {"ok": True})


class TestHttpServer:
    def __enter__(self):
        self.received_payload = None
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/json":
                    self._send(200, b'{"ok": true}', "application/json")
                    return
                if self.path == "/text":
                    self._send(200, b"hello", "text/plain")
                    return
                self._send(404, b"not found", "text/plain")

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.received_payload = json.loads(body.decode("utf-8"))
                self._send(204, b"", "text/plain")

            def log_message(self, format, *args):
                return

            def _send(self, status, body, content_type):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()


if __name__ == "__main__":
    unittest.main()
