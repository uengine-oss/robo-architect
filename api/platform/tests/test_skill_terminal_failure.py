from api.platform.skill_runner import skill_terminal_failure


def test_session_limit_is_not_misreported_as_json_parse_failure():
    error = skill_terminal_failure(
        "You've hit your session limit · resets 7:50pm (Asia/Seoul)"
    )
    assert error["code"] == "LLM_SESSION_LIMIT"
    assert "7:50pm" in error["message"]


def test_normal_model_output_has_no_terminal_failure():
    assert skill_terminal_failure('{"action":"done"}') is None
