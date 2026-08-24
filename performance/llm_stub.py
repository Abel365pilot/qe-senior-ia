"""Emulador de un endpoint de chat. Uso: python3 llm_stub.py [puerto]
Ajustable por variables de entorno: TPM, MAX_CONC, BASE_MS, MS_PER_TOK.
"""
import json, os, random, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TPM        = int(os.getenv("TPM", "100000"))      # cuota de tokens por minuto
MAX_CONC   = int(os.getenv("MAX_CONC", "4"))      # peticiones atendidas en paralelo
BASE_MS    = int(os.getenv("BASE_MS", "250"))     # latencia base
MS_PER_TOK = float(os.getenv("MS_PER_TOK", "8"))  # latencia por token generado

_lock = threading.Lock()
_slots = threading.Semaphore(MAX_CONC)
_ventana = time.monotonic()
_usados = 0


def _reservar(tokens):
    """None si hay cuota; si no, segundos que faltan para la siguiente ventana."""
    global _ventana, _usados
    with _lock:
        ahora = time.monotonic()
        if ahora - _ventana >= 60:
            _ventana, _usados = ahora, 0
        if _usados + tokens > TPM:
            return max(1, int(60 - (ahora - _ventana)))
        _usados += tokens
        return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _responder(self, codigo, cuerpo, extra=None):
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(datos)

    def do_POST(self):
        if self.path != "/chat/completions":
            return self._responder(404, {"error": "not_found"})
        n = int(self.headers.get("Content-Length", 0))
        try:
            pet = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._responder(400, {"error": "json_invalido"})

        salida = int(pet.get("max_tokens", 128))
        entrada = sum(len(m.get("content", "")) for m in pet.get("messages", [])) // 4
        espera = _reservar(entrada + salida)
        if espera is not None:
            return self._responder(429, {"error": "rate_limit_exceeded"},
                                   {"Retry-After": str(espera)})

        with _slots:                      # por encima de MAX_CONC, las peticiones encolan
            demora = (BASE_MS + salida * MS_PER_TOK) * random.uniform(0.85, 1.15)
            time.sleep(demora / 1000.0)

        self._responder(200, {
            "id": "stub", "object": "chat.completion",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "x" * salida}}],
            "usage": {"prompt_tokens": entrada, "completion_tokens": salida,
                      "total_tokens": entrada + salida},
        })

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"escuchando en :{puerto}  TPM={TPM} MAX_CONC={MAX_CONC}")
    ThreadingHTTPServer(("", puerto), Handler).serve_forever()
