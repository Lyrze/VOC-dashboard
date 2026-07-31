# -*- coding: utf-8 -*-
"""
VOC Dashboard - local AI bridge (Claude Code CLI)

Exposes a tiny HTTP server that forwards prompts to the Claude Code CLI
installed on this machine, so the browser dashboard can use AI without
sending data to a third-party API endpoint.

Endpoints
    GET  /health -> {"ok": true, "backend": "claude-code-cli"}
    POST /ask    -> {"prompt": "..."}  =>  {"text": "..."}
    POST /v1/chat/completions          (OpenAI-compatible shape, same backend)

Notes
    - Uses your own Claude subscription usage (tokens).
    - Keep this window open; closing it stops the AI features.
    - Binds to 127.0.0.1 only. Not reachable from other machines.
"""

import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8799
TIMEOUT_SEC = 300

# Only one CLI call at a time - the CLI is not built for parallel sessions.
_lock = threading.Lock()


def find_claude():
    for name in ("claude", "claude.cmd", "claude.exe"):
        p = shutil.which(name)
        if p:
            return p
    return None


CLAUDE = find_claude()


def ask_claude(prompt):
    if not CLAUDE:
        raise RuntimeError(
            "Claude Code CLI not found. Install it first:\n"
            "  npm install -g @anthropic-ai/claude-code"
        )
    # Pass the prompt on stdin, not argv.
    # On Windows the CLI is a .CMD shim, so a long multi-line argv gets
    # mangled/truncated by cmd.exe - the model then sees only the first line.
    with _lock:
        proc = subprocess.run(
            [CLAUDE, "-p"],
            input=prompt,
            capture_output=True,
            timeout=TIMEOUT_SEC,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    if proc.returncode != 0:
        err = (proc.stderr or "").strip() or "exit code %d" % proc.returncode
        raise RuntimeError("Claude CLI error: " + err[:500])
    out = (proc.stdout or "").strip()
    if not out:
        raise RuntimeError("Claude CLI returned an empty response.")
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # --- helpers -------------------------------------------------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, fmt, *args):
        sys.stdout.write("  %s\n" % (fmt % args))
        sys.stdout.flush()

    # --- routes --------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/health"):
            self._json(200, {"ok": bool(CLAUDE), "backend": "claude-code-cli", "cli": CLAUDE or ""})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        data = self._read_json()

        if self.path.startswith("/ask"):
            prompt = (data.get("prompt") or "").strip()
            if not prompt:
                return self._json(400, {"error": "prompt is required"})
            try:
                return self._json(200, {"text": ask_claude(prompt)})
            except Exception as e:
                return self._json(500, {"error": str(e)})

        if self.path.startswith("/v1/chat/completions"):
            msgs = data.get("messages") or []
            prompt = "\n\n".join(
                (m.get("content") or "") for m in msgs if m.get("role") != "system"
            ).strip()
            if not prompt:
                return self._json(400, {"error": "messages is required"})
            try:
                text = ask_claude(prompt)
            except Exception as e:
                return self._json(500, {"error": str(e)})
            return self._json(200, {
                "id": "chatcmpl-local",
                "object": "chat.completion",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }],
            })

        self._json(404, {"error": "not found"})


def main():
    print("=" * 58)
    print("  VOC Dashboard - local AI bridge")
    print("=" * 58)
    if CLAUDE:
        print("  AI backend : Claude Code CLI  ...  ready")
        print("  CLI path   : %s" % CLAUDE)
    else:
        print("  [!] Claude Code CLI not found.")
        print("      npm install -g @anthropic-ai/claude-code")
    print("  URL        : http://localhost:%d" % PORT)
    print("  Paste that URL into the dashboard: AI settings > Claude CLI")
    print("  Keep this window open. Closing it stops the AI features.")
    print("=" * 58)
    sys.stdout.flush()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  stopped.")
