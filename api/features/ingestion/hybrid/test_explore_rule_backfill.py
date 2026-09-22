import asyncio
from unittest.mock import patch

from api.features.ingestion.hybrid import explore_service


def test_empty_analyzer_rules_reports_error_instead_of_success():
    events = []

    async def sink(event):
        events.append(event)

    async def no_rules(*_args, **_kwargs):
        return []

    with (
        patch.object(explore_service, "fetch_session_snapshot", return_value={
            "processes": [{"id": "process-1"}], "rules": [],
        }),
        patch.object(explore_service, "extract_rules_from_analyzer_graph", no_rules),
        patch.object(explore_service, "save_rules") as save,
    ):
        result = asyncio.run(explore_service._ensure_session_rules("session-1", sink))

    assert result is False
    assert events[0]["type"] == "AgentError"
    save.assert_not_called()
