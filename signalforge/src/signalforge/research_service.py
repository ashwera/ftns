"""Local-only API. Run: PYTHONPATH=signalforge/src python3 -m signalforge.research_service"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlsplit
from pathlib import Path
import re
from .research_session import ResearchSessions

HOSTS = {"127.0.0.1:8765", "localhost:8765"}
ORIGINS = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (5173, 8765)}


def handler(sessions):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            if self.headers.get("Host") not in HOSTS or (self.headers.get("Origin") is not None and self.headers["Origin"] not in ORIGINS):
                self.reply(403, {"error": "Local host/origin required"})
                return False
            return True

        def do_POST(self):
            if not self.allowed():
                return
            if self.path != "/api/agent/runs":
                return self.reply(404, {"error": "Unknown endpoint"})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json" or self.headers.get("Transfer-Encoding"):
                return self.reply(415, {"error": "JSON required"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 20000:
                    raise ValueError("Invalid request size")
                self.connection.settimeout(5)
                payload = json.loads(self.rfile.read(size))
                result = sessions.start(payload)
            except (ValueError, UnicodeError):
                return self.reply(400, {"error": "Supply company (1–200 characters) and prompt (1–4000 characters) only"})
            except RuntimeError:
                return self.reply(409, {"error": "A research run is already active"})
            self.reply(202, result)

        def do_GET(self):
            if not self.allowed():
                return
            if self.path == "/api/agent/runs":
                return self.reply(200, sessions.list_runs())
            prefix = "/api/agent/runs/"
            if not self.path.startswith(prefix) or urlsplit(self.path).query:
                return self.reply(404, {"error": "Unknown endpoint"})
            artifact = re.fullmatch(r'(research_\d{8}T\d{6}_[a-f0-9]{12})/artifacts/(f1\.json|r1\.json|investigation\.json|investigation_review\.json|machine_evidence_report\.json)',self.path[len(prefix):])
            if artifact:
                try:
                    sessions.get(artifact[1])
                    value=json.loads((sessions.root/artifact[1]/artifact[2]).read_text())
                except (KeyError,OSError,ValueError):
                    return self.reply(404,{'error':'Report artifact unavailable'})
                return self.reply(200,value)
            try:
                result = sessions.get(self.path[len(prefix):])
            except KeyError:
                return self.reply(404, {"error": "Run not found"})
            self.reply(200, result)
    return Handler


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), handler(ResearchSessions()))
    print("Research service listening on http://127.0.0.1:8765")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
