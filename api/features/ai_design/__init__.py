"""
AI Design (open-pencil AI proxy).

Backend-side LLM proxy for the open-pencil AI chat (used by the Inspector
Design tab's "OpenPencil AI로 생성" path). The proxy is OpenAI-compatible:
the frontend points open-pencil at this prefix via the `openai-compatible`
provider and the calls flow through `api/platform/llm.py`, honoring the
project's central `LLM_PROVIDER` / `LLM_MODEL` / `*_API_KEY` env config.

Constitution VI is satisfied because every LLM call now goes through the
runtime abstraction; tools and tool execution still run browser-side
(open-pencil's tools mutate a live Vue store + renderer + undo stack).

Endpoints:
  POST /api/ai-design/v1/chat/completions   → OpenAI-compatible chat (streaming)
  GET  /api/ai-design/health                → ops/debug only — backend self-check
                                              (the frontend bootstrap is purely
                                              static and does NOT call this)
"""
