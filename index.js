#!/usr/bin/env node
/**
 * dsv4-subagent-fix — Minimal DeepSeek V4 Subagent Fix Proxy
 *
 * Strips `output_config` and `reasoning_effort` from subagent requests
 * (thinking.type=disabled) to fix Claude Code ≥ 2.1.166 compatibility.
 * Main agent requests pass through untouched.
 *
 * Zero dependencies. Node.js ≥ 18 built-in modules only.
 *
 * Usage:
 *   npx dsv4-subagent-fix
 *   node index.js
 */

const http = require("http");
const https = require("https");

const UPSTREAM = "https://api.deepseek.com/anthropic";
const PORT = 16890;
const BIND = "127.0.0.1";

const server = http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", () => {
    const body = Buffer.concat(chunks);
    const bodyStr = body.length > 0 ? body.toString("utf8") : "";

    const fwdHeaders = {};
    for (const [k, v] of Object.entries(req.headers)) {
      if (k.toLowerCase() !== "host") fwdHeaders[k] = v;
    }

    let modifiedBody = body;
    const pathNoQuery = req.url.split("?")[0].replace(/\/+$/, "");
    const isMessages =
      req.method === "POST" && pathNoQuery.endsWith("/messages");

    if (isMessages && bodyStr) {
      try {
        const data = JSON.parse(bodyStr);
        const model = data.model || "";
        const thinking = data.thinking || {};

        if (model.startsWith("deepseek-v4") && thinking.type === "disabled") {
          let stripped = [];
          for (const key of ["reasoning_effort", "output_config"]) {
            if (data[key] !== undefined) {
              stripped.push(`${key}=${JSON.stringify(data[key])}`);
              delete data[key];
            }
          }
          if (stripped.length > 0) {
            const newBody = JSON.stringify(data);
            modifiedBody = Buffer.from(newBody, "utf8");
            fwdHeaders["content-length"] = String(Buffer.byteLength(newBody));
            console.log(`[FIX] stripped ${stripped.join(", ")}`);
          }
        }
      } catch (e) {
        // Invalid JSON, pass through
      }
    }

    const upstreamUrl = UPSTREAM + req.url;
    const upstreamReq = https.request(
      upstreamUrl,
      { method: req.method, headers: fwdHeaders, timeout: 600_000 },
      (upstreamRes) => {
        res.writeHead(upstreamRes.statusCode, upstreamRes.headers);
        upstreamRes.pipe(res);
      }
    );

    upstreamReq.on("error", (err) => {
      if (!res.headersSent) {
        res.writeHead(502, { "Content-Type": "application/json" });
      }
      res.end(JSON.stringify({ error: String(err) }));
    });

    upstreamReq.write(modifiedBody);
    upstreamReq.end();
  });
});

server.listen(PORT, BIND, () => {
  console.log(`dsv4-subagent-fix → ${BIND}:${PORT} (upstream: ${UPSTREAM})`);
});
