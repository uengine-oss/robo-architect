/** Unit tests for the Architect API's LLM settings in a packaged app (src/main/llm-bridge-env.ts). */

import { expect, test } from "@playwright/test";
import { llmBridgeEnv } from "../../src/main/llm-bridge-env";

test.describe("llmBridgeEnv", () => {
  test("no key: the backend goes to its own Claude Code bridge on its own port", () => {
    expect(llmBridgeEnv({}, 50709)).toEqual({
      OPENAI_API_KEY: "claude-code-bridge",
      OPENAI_BASE_URL: "http://127.0.0.1:50709/api/llm-bridge/v1",
      LLM_MODEL: "claude-code",
    });
  });

  test("a blank key counts as no key", () => {
    expect(llmBridgeEnv({ OPENAI_API_KEY: "  " }, 1).OPENAI_BASE_URL).toContain("/api/llm-bridge/v1");
  });

  test("a stale LLM_MODEL does not reach the bridge", () => {
    expect(llmBridgeEnv({ LLM_MODEL: "gpt-4.1" }, 1).LLM_MODEL).toBe("claude-code");
  });

  test("LLM_API_KEY alone is the catalog's name, the Architect API still needs the bridge", () => {
    expect(llmBridgeEnv({ LLM_API_KEY: "k" }, 1).OPENAI_API_KEY).toBe("claude-code-bridge");
  });

  for (const name of ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"]) {
    test(`${name} set: nothing is overridden`, () => {
      expect(llmBridgeEnv({ [name]: "configured" }, 1)).toEqual({});
    });
  }
});
