/**
 * AI Design bootstrap — wire open-pencil's AI provider to the backend proxy.
 *
 * The backend at `/api/ai-design/v1/chat/completions` is the single source of
 * truth for provider/model/credentials (driven by `.env` LLM_PROVIDER /
 * LLM_MODEL / *_API_KEY). The frontend only needs to tell open-pencil's
 * existing `@ai-sdk/openai`-based client where to send requests.
 *
 * Why localStorage at all? open-pencil's `useAIChat` reads its config from
 * these keys to decide which SDK to instantiate (`createOpenAI({apiKey,
 * baseURL})` for `openai-compatible`). We populate them with non-secret
 * plumbing values:
 *
 *   - provider:    "openai-compatible"          ← selects the SDK
 *   - base-url:    "<origin>/api/ai-design/v1"  ← routes HTTP to our proxy
 *                                                 (openai-compatible SDKs append
 *                                                 /chat/completions to this; the
 *                                                 /v1 segment must be in the base)
 *   - api-type:    "completions"                ← Chat Completions, not /responses
 *   - api-key:     "proxy"                      ← placeholder; backend ignores
 *   - custom-model:"backend-managed"            ← placeholder; backend ignores
 *
 * No request to the backend is needed for any of this. The real model name,
 * provider, and API key live exclusively on the backend and never reach the
 * browser.
 */

const PROVIDER_ID = 'openai-compatible'
const PLACEHOLDER_API_KEY = 'proxy'
const PLACEHOLDER_MODEL_ID = 'backend-managed'

const STORAGE = {
  provider: 'open-pencil:ai-provider',
  apiType: 'open-pencil:ai-api-type',
  baseUrl: 'open-pencil:ai-base-url',
  customModel: 'open-pencil:ai-custom-model',
  apiKey: `open-pencil:ai-key:${PROVIDER_ID}`,
}

function backendBaseUrl() {
  // The `/v1` segment is part of the base by OpenAI-SDK convention; the SDK
  // appends `/chat/completions` to whatever we provide here.
  return window.location.origin.replace(/\/$/, '') + '/api/ai-design/v1'
}

export function bootstrapAIDesign({ force = false } = {}) {
  // Skip if already pointing at our proxy (lets a user override via the
  // open-pencil settings UI temporarily without us silently rewriting).
  const alreadySet =
    localStorage.getItem(STORAGE.provider) === PROVIDER_ID &&
    localStorage.getItem(STORAGE.baseUrl) &&
    localStorage.getItem(STORAGE.apiKey)
  if (alreadySet && !force) {
    return { ok: true, source: 'cached' }
  }

  localStorage.setItem(STORAGE.provider, PROVIDER_ID)
  localStorage.setItem(STORAGE.baseUrl, backendBaseUrl())
  localStorage.setItem(STORAGE.apiType, 'completions')
  localStorage.setItem(STORAGE.apiKey, PLACEHOLDER_API_KEY)
  localStorage.setItem(STORAGE.customModel, PLACEHOLDER_MODEL_ID)

  console.info('[ai-design] open-pencil wired to backend proxy', {
    baseUrl: backendBaseUrl(),
  })

  return { ok: true, source: 'static' }
}
