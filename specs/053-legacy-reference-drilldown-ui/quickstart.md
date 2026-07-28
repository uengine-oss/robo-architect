# Quickstart / Verification

1. Run provenance unit tests including out-of-order/interleaved tool IDs, multiple details, errors and old v1 records.
2. Run Proposal API tests for list/detail serialization.
3. Start Analyzer/Architect and execute one intent, one plan and one staged DDD path that call both MCP tools.
4. Compare saved searched/inspected IDs and source lines to live Analyzer/Neo4j.
5. Build frontend and run Playwright for list badge, chip, collapsed/expanded details and ②-B line states.
6. Check console/network errors, keyboard toggle, unrelated proposal rows and pre-existing chip behavior.
7. Grep active `LEGACYQ|LEGACYREF` legacy-only parsing and duplicated collector loops; retain only intentional v1 read compatibility/tests.
8. For INTENT, record tool-use evidence that the skill reads `strategic-output-schema.md`, `bounded-contexts.md`, and `legacy-reference.md`; assert at least one search and, when candidates exist, one successful detail. Reject output containing top-level `tacticalDiff`.
