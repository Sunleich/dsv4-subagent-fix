#!/usr/bin/env python3
"""极简 DeepSeek 子代理修复代理

只做一件事：子代理请求中 thinking.type=disabled 时，剔除 output_config 和
reasoning_effort（DeepSeek 禁止与 disabled 共存，会返回 400）。

主代理（thinking=enabled/adaptive）及其他请求完全透传，零修改。

使用方法:
  python3 ~/.claude/scripts/dsv4-subagent-fix.py &
  # settings.json 中设置: "ANTHROPIC_BASE_URL": "http://localhost:16890"
  # systemd 自启见下方
"""

import http.server
import json
import os
import ssl
import urllib.error
import urllib.request

UPSTREAM = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/anthropic")
PORT = 16890
BIND = "127.0.0.1"


class Handler(http.server.BaseHTTPRequestHandler):
    def _proxy(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b""

        fwd_headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}

        # 仅拦截 POST /v1/messages（去掉 ?query 后缀）
        path_no_query = self.path.split("?")[0].rstrip("/")
        if self.command == "POST" and path_no_query.endswith("/messages") and body:
            try:
                data = json.loads(body)
                model = data.get("model", "")
                thinking = data.get("thinking", {})

                if (
                    isinstance(model, str)
                    and model.startswith("deepseek-v4")
                    and isinstance(thinking, dict)
                    and thinking.get("type") == "disabled"
                ):
                    stripped = []
                    for key in ("reasoning_effort", "output_config"):
                        if key in data:
                            val = data.pop(key)
                            stripped.append(f"{key}={val}")
                    if stripped:
                        body = json.dumps(data).encode("utf-8")
                        fwd_headers["content-length"] = str(len(body))
                        self.log_message("[FIX] stripped %s", ", ".join(stripped))
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        # 转发到上游
        url = f"{UPSTREAM}{self.path}"
        req = urllib.request.Request(url, data=body, headers=fwd_headers, method=self.command)

        try:
            ctx = ssl.create_default_context()
            resp = urllib.request.urlopen(req, context=ctx, timeout=600)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
            return
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        self.send_response(resp.status)
        for k, v in resp.headers.items():
            if k.lower() not in ("transfer-encoding", "content-encoding"):
                self.send_header(k, v)
        self.end_headers()

        while True:
            chunk = resp.read(8192)
            if not chunk:
                break
            self.wfile.write(chunk)

    do_GET = _proxy
    do_POST = _proxy
    do_PUT = _proxy
    do_DELETE = _proxy
    do_PATCH = _proxy
    do_OPTIONS = _proxy

    def log_message(self, fmt, *args):
        msg = fmt % args if args else fmt
        print(f"[{self.command}] {msg}", flush=True)


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"dsv4-subagent-fix → {BIND}:{PORT} (upstream: {UPSTREAM})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
