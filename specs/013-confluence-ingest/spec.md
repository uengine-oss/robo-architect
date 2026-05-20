# Feature Specification: Confluence Page Ingestion

**Feature Branch**: `013-confluence-ingest`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/ingestion/confluence.py`, `api/main.py` (router registration), `frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue`

## User Scenarios & Testing

### User Story 1 - Connect to Confluence and list pages (Priority: P1)

The architect opens the requirements ingestion modal and chooses Confluence as the input source. They enter their Atlassian email, an API token, and a Cloud base URL (default `https://uengine-team.atlassian.net`). They click "List pages". The backend tries the v1 REST API (`/wiki/rest/api/content`) first; if that returns 404 it falls back to v2 (`/wiki/api/v2/pages`). Pagination is followed until exhausted. The user sees a list of pages with `id`, `title`, `status`, and `spaceId` to choose from.

**Why this priority**: Without listing, the user cannot pick which page to ingest. This is the gateway capability for the whole feature.

**Independent Test**: `POST /api/ingest/confluence/pages` with valid credentials and verify the response shape `{pages: [{id, title, status, spaceId}], total: N}` and that bad credentials yield `401` with a Korean detail string.

**Acceptance Scenarios**:

1. **Given** valid credentials and a Cloud site that supports v1, **When** `POST /api/ingest/confluence/pages` is called, **Then** the response includes every page returned by v1 across paginated `_links.next` calls.
2. **Given** a site where v1 returns 404, **When** the same call is made, **Then** the backend transparently falls back to v2 and the user sees the v2 page list with no error.
3. **Given** an invalid token, **When** the call is made, **Then** the response is `401` with detail `인증 실패: 이메일 또는 API 토큰을 확인하세요.`
4. **Given** the user has no permission to list content, **When** Confluence returns 403, **Then** the response is `403` with `접근 권한이 없습니다.` plus the offending URL.

### User Story 2 - Fetch a page's content as plain text (Priority: P1)

After choosing a page, the user requests its body. The backend calls v1 `/wiki/rest/api/content/{id}?expand=body.storage`, falls back to v2 `/wiki/api/v2/pages/{id}?body-format=storage` if v1 returns 404, and converts the returned Confluence "storage format" HTML to plain text via a custom `HTMLParser` that emits newlines for block tags (`p`, `div`, `li`, `tr`, `h1..h6`, `br`) and a `"  - "` bullet for `li`.

**Why this priority**: The whole point of the feature is to feed Confluence text into the requirements pipeline; without content extraction, the listing is dead weight.

**Independent Test**: `POST /api/ingest/confluence/page-content` with a real `page_id` and verify the response includes `title`, plain-text `content`, and `content_length`. Confirm `<p>Hello</p><ul><li>x</li></ul>` becomes a multi-line plain string with a `"  - x"` bullet.

**Acceptance Scenarios**:

1. **Given** an existing page on a v1-enabled site, **When** content is requested, **Then** the response is `{page_id, title, content, content_length}` with `content` containing only readable text (no HTML tags).
2. **Given** an existing page that v1 cannot find but v2 can, **When** content is requested, **Then** v2 is used transparently and the response is identical in shape.
3. **Given** a page id that does not exist on either API, **When** content is requested, **Then** the response is `404` `페이지를 찾을 수 없습니다.`
4. **Given** a Confluence connection error (timeout, DNS failure), **When** content is requested, **Then** the response is `502` `Confluence 연결 실패: ...`.

### User Story 3 - Drive ingestion from the requirements modal (Priority: P2)

In the `RequirementsIngestionModal`, the user picks the JIRA/Confluence input mode. Credentials are persisted to `localStorage` under `jira_confluence_creds` so the user does not retype on every visit. The fetched page text becomes one of the input documents handed to the requirement ingestion pipeline (which produces user stories, BCs, etc.) — Confluence is treated as a source on equal footing with file uploads, pasted text, JIRA, and Figma.

**Why this priority**: This is the UX glue. The endpoints work without it, but real users only reach them through this flow.

**Independent Test**: Open the requirements modal, select Confluence, save credentials, list pages, fetch one, and confirm the resulting text appears in the ingestion input area.

### Edge Cases

- The user supplies a `base_url` with a trailing slash — `_list_pages_v1`/`_list_pages_v2` strip it via `.rstrip("/")`.
- A page body is empty (`storage.value` is `""` or missing) — `_html_to_text` is skipped and `content` is returned as an empty string with `content_length: 0`.
- `_links.next` returns a relative path — the loop reconstructs the absolute URL by prefixing the stripped base.
- The Confluence storage format includes inline tags like `<strong>`/`<em>` — they are passed through as text without explicit handling, leaving readable inline content.
- A 401 or 403 occurs mid-pagination — the auth check at the top of each loop body raises immediately so partial results are not returned.
- An unexpected exception type (not `HTTPException`/`HTTPStatusError`/`RequestError`) is converted to `502 Confluence 오류: {Type}: {message}` so the frontend always gets a deterministic error envelope.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `POST /api/ingest/confluence/pages` accepting `{email, api_token, base_url}` (Pydantic `ConfluenceCredentials`, `base_url` defaulting to `https://uengine-team.atlassian.net`).
- **FR-002**: System MUST attempt the Confluence v1 REST API (`/wiki/rest/api/content`) first and only fall back to v2 (`/wiki/api/v2/pages`) when v1 responds `404`.
- **FR-003**: System MUST follow pagination via `_links.next` for both v1 and v2 listings, accumulating every page until the cursor is exhausted.
- **FR-004**: System MUST authenticate using HTTP Basic Auth (`email`, `api_token`) and request `Accept: application/json`.
- **FR-005**: System MUST raise structured `HTTPException`s for authentication failures: `401` with `인증 실패: 이메일 또는 API 토큰을 확인하세요.` and `403` with `접근 권한이 없습니다. (URL: {url})`.
- **FR-006**: System MUST log Confluence operations to `SmartLogger` with categories `confluence.pages.request`, `confluence.pages.done`, `confluence.pages.error`, `confluence.page_content.error`, and `confluence.auth`, redacting the token to a length and 8-char prefix only.
- **FR-007**: System MUST expose `POST /api/ingest/confluence/page-content` accepting `{email, api_token, base_url, page_id}` (Pydantic `PageFetchRequest`).
- **FR-008**: System MUST request the page body in `storage` format on both v1 (`expand=body.storage`) and v2 (`body-format=storage`) and convert the HTML to plain text before returning.
- **FR-009**: HTML-to-text conversion MUST emit newline boundaries for `p`, `div`, `li`, `tr`, `h1..h6`, and `br`, and prefix `li` text with `"  - "` to preserve list structure.
- **FR-010**: System MUST translate `httpx.HTTPStatusError` to `502 Confluence API 오류: {status_code}` and `httpx.RequestError` to `502 Confluence 연결 실패: {message}`; any other exception MUST become `502 Confluence 오류: {Type}: {message}`.
- **FR-011**: System MUST register the Confluence router in `api/main.py` (`include_router(confluence_router)`) so endpoints live under the `/api/ingest/confluence` prefix.
- **FR-012**: The frontend ingestion modal MUST persist Confluence credentials in `localStorage` under the key `jira_confluence_creds` and offer Confluence as one of the selectable `inputMode` values alongside `file`, `text`, `jira`, `figma`, and `analyzer`.

### Key Entities

- **ConfluenceCredentials** (Pydantic): `{email, api_token, base_url}`; the request body for listing pages.
- **PageFetchRequest** (Pydantic): `{email, api_token, base_url, page_id}`; the request body for fetching a single page.
- **ConfluencePage** (response shape): `{id, title, status, spaceId}`; spaceId is sourced from `space.key` on v1 and `spaceId` on v2.
- **PageContent** (response shape): `{page_id, title, content, content_length}`.
- **_HTMLTextExtractor** (Python class): subclass of `html.parser.HTMLParser` that turns Confluence storage-format HTML into newline-delimited plain text.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user with valid credentials lists every page in their Confluence Cloud space across pagination boundaries with no manual cursor handling.
- **SC-002**: The list endpoint succeeds against both Confluence Cloud sites that expose v1 and sites that only expose v2 — without the user having to choose an API version.
- **SC-003**: At least 95% of ingested page bodies render to plain text whose length matches the user's mental model (block elements separated by newlines; bulleted lists prefixed with `"  - "`).
- **SC-004**: All Confluence error paths return an `HTTPException` with a 4xx/5xx status and a Korean detail string — the frontend never has to parse generic 500 responses.
- **SC-005**: API tokens never appear in logs in cleartext: only token length and an 8-character prefix are recorded.

## Assumptions

- The target Confluence deployment is Atlassian Cloud (REST v1 and/or v2) — Server/Data Center installations are out of scope.
- Email + API token Basic Auth is sufficient; OAuth/SSO flows are not implemented.
- Page bodies fit in memory and within the 30-second `httpx` client timeout configured for both endpoints.
- Confluence storage-format HTML is well-formed enough for `html.parser.HTMLParser` to consume; macro/embed content surfaces as plain text fragments without special expansion.
- Downstream ingestion treats Confluence text identically to other text sources (no Confluence-specific markup preservation).
- Token storage in `localStorage` (`jira_confluence_creds`) is acceptable for this single-user, self-hosted deployment model.
