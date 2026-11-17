/**
 * The Architect API's LLM settings in a packaged app.
 *
 * `api/platform/llm.py` get_llm() runs on `LLM_PROVIDER=openai` and fails without `OPENAI_API_KEY`,
 * so a keyless install could not generate a wireframe: measured 2026-11-05 on the 0.1.2 build,
 * both `/api/ai-design/wireframe/{id}` and `/api/graph/generate-component-wireframe/{id}` failed with
 * the SDK's missing api_key error. Without a key, this points get_llm() at the app's own OpenAI-compatible
 * `/api/llm-bridge/v1`, which answers with the Claude Code on this PC — the analyzer's route too.
 *
 * Someone who configured an OpenAI key or an OpenAI-compatible server keeps what they configured.
 * These values go to the backend's environment only: the shell's AI key row reads this process's
 * environment, so setting them here would report a placeholder as a configured key.
 */

/** What api/features/llm_bridge/router.py replaces with its own default Claude model. */
const BRIDGE_MODEL = "claude-code";
/** Never sent anywhere: the bridge does not read it, the OpenAI client only needs one to start. */
const BRIDGE_API_KEY = "claude-code-bridge";

function isSet(value: string | undefined): boolean {
  return (value ?? "").trim() !== "";
}

export function llmBridgeEnv(env: NodeJS.ProcessEnv, port: number): NodeJS.ProcessEnv {
  if (isSet(env.OPENAI_API_KEY) || isSet(env.OPENAI_BASE_URL) || isSet(env.OPENAI_API_BASE)) {
    return {};
  }
  return {
    OPENAI_API_KEY: BRIDGE_API_KEY,
    OPENAI_BASE_URL: `http://127.0.0.1:${port}/api/llm-bridge/v1`,
    LLM_MODEL: BRIDGE_MODEL,
  };
}
