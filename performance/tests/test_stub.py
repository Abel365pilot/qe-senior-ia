import http.client
import json
import threading
import time
import unittest

import llm_stub


class StubContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = llm_stub.ThreadingHTTPServer(("127.0.0.1", 0), llm_stub.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        llm_stub.TPM = 1000
        llm_stub.MAX_CONC = 2
        llm_stub.BASE_MS = 0
        llm_stub.MS_PER_TOK = 0
        llm_stub._slots = threading.Semaphore(llm_stub.MAX_CONC)
        llm_stub._ventana = time.monotonic()
        llm_stub._usados = 0

    def post(self, path, body, *, raw=False):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        payload = body if raw else json.dumps(body)
        connection.request("POST", path, body=payload, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        data = json.loads(response.read())
        headers = dict(response.getheaders())
        connection.close()
        return response.status, headers, data

    def test_success_contract_and_token_accounting(self):
        prompt = "hola mundo"
        status, _, body = self.post(
            "/chat/completions",
            {"messages": [{"role": "user", "content": prompt}], "max_tokens": 4},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["object"], "chat.completion")
        self.assertEqual(body["choices"][0]["message"]["content"], "xxxx")
        self.assertEqual(body["usage"]["prompt_tokens"], len(prompt) // 4)
        self.assertEqual(body["usage"]["completion_tokens"], 4)
        self.assertEqual(body["usage"]["total_tokens"], len(prompt) // 4 + 4)

    def test_invalid_json_returns_400(self):
        status, _, body = self.post("/chat/completions", "{", raw=True)
        self.assertEqual(status, 400)
        self.assertEqual(body, {"error": "json_invalido"})

    def test_unknown_path_returns_404(self):
        status, _, body = self.post("/otra-ruta", {})
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "not_found"})

    def test_tpm_limit_returns_429_and_retry_after(self):
        llm_stub.TPM = 2
        request = {"messages": [], "max_tokens": 2}
        first_status, _, _ = self.post("/chat/completions", request)
        second_status, headers, body = self.post("/chat/completions", request)
        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 429)
        self.assertEqual(body, {"error": "rate_limit_exceeded"})
        self.assertGreaterEqual(int(headers["Retry-After"]), 1)

    def test_token_window_resets_after_sixty_seconds(self):
        llm_stub.TPM = 10
        llm_stub._usados = 10
        llm_stub._ventana = time.monotonic() - 61
        self.assertIsNone(llm_stub._reservar(4))
        self.assertEqual(llm_stub._usados, 4)


if __name__ == "__main__":
    unittest.main()
