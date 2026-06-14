# dsv4-subagent-fix

A minimal (zero dependencies) local proxy that fixes DeepSeek V4's subagent incompatibility with Claude Code ≥ 2.1.166, with runtime upstream switching support.

## Quick Start

```bash
npx dsv4-subagent-fix
```

Then add to Claude Code `settings.json`:

```json
"ANTHROPIC_BASE_URL": "http://localhost:16890"
```

Restart Claude Code. Subagents work.

**Python version (no npm needed):**
```bash
python3 dsv4_subagent_fix.py &
```

## Problem

Claude Code 2.1.166+ sends `thinking: { type: "disabled" }` for subagents (no need to show thinking chain to users). When combined with `CLAUDE_CODE_EFFORT_LEVEL=max` (recommended by DeepSeek), the API request includes `output_config` or `reasoning_effort`. DeepSeek's Anthropic-compatible endpoint rejects this combination:

> thinking options type cannot be disabled when reasoning_effort is set

This breaks ALL Claude Code subagent/Workflow functionality.

[Official DeepSeek issue #1397](https://github.com/deepseek-ai/DeepSeek-V3/issues/1397)

## Solution

A single-purpose local proxy on `localhost:16890` that strips `output_config` and `reasoning_effort` from subagent requests only. Main agent requests (`thinking.type=enabled/adaptive`) pass through completely untouched.

```
Claude Code (subagent)
  → localhost:16890
    strip output_config / reasoning_effort
  → api.deepseek.com/anthropic (200 OK)

Claude Code (main agent)
  → localhost:16890
    (passthrough, unchanged)
  → api.deepseek.com/anthropic
```

## Switching Upstream (Runtime)

The proxy supports changing the upstream API URL at runtime without restarting.

```bash
# Check current upstream
curl http://localhost:16890/__status

# Switch to a different API
curl -X POST http://localhost:16890/__switch \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://your-api.com/v1"}'
```

**Priority at startup:** `-u <url>` CLI arg > `DEEPSEEK_API_URL` env var > default (`https://api.deepseek.com/anthropic`)

```bash
# Via env var
DEEPSEEK_API_URL=https://your-api.com/v1 npx dsv4-subagent-fix

# Via CLI arg
npx dsv4-subagent-fix -u https://your-api.com/v1
```

## Auto-start with systemd

```bash
sudo cp dsv4-subagent-fix.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dsv4-subagent-fix
```

To set a custom upstream via systemd, add to the service file:

```ini
[Service]
Environment="DEEPSEEK_API_URL=https://your-api.com/v1"
```

## Why not dsv4-cc-proxy?

[dsv4-cc-proxy](https://github.com/HosheaLi/dsv4-cc-proxy) is a more comprehensive proxy that fixes 3 API incompatibilities. However, its thinking normalization applies to ALL requests, which can affect main agent reasoning quality. This script takes a more conservative approach — only strip conflicting fields when `thinking.type=disabled`, leaving main agent requests completely untouched.

| | dsv4-cc-proxy | dsv4-subagent-fix |
|---|---|---|
| Lines of code | ~430 | **~130** |
| Dependencies | httpx, starlette, socksio... | **Node.js / Python stdlib only** |
| Main agent impact | Side effects | **None (passthrough)** |
| What it fixes | 3 issues | **1 focused fix** |
| Runtime switch | ❌ | **Built-in (HTTP endpoint)** |

## License

MIT
