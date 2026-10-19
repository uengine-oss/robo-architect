# -*- coding: utf-8 -*-
"""정책 이름 읽기 — **축약을 오배선이라 부르지 않는다** (§291).

2026-10-19 에 배선 검사가 2건을 *"이름의 사건이 **아예 없습니다**"* 로 띄웠다.
그 문구는 10-16 에 **진짜 오배선**에 붙던 가장 센 신호다. 그런데 실제로는 둘 다
`…OnMonthlyAttendanceClosing` 인데 걸린 사건이 `MonthlyAttendanceClosingConfirmed`
였다 — **빠진 것은 낱말 하나**였다.

이 파일이 있는 이유: 그때 두 함수가 **닫힌 함수 안에** 있어서 테스트를 못 썼고,
그래서 화면에 뜬 뒤에야 알았다. 밖으로 꺼내면서 같이 쓴다.
"""

from api.features.ingestion.ingestion_workflow_runner import (
    policy_name_is_abbrev,
    policy_name_says,
)


class Test이름이_말하는_사건:
    def test_동작On사건_꼴(self):
        assert (policy_name_says("GrantAnnualLeaveOnLeaveApplicationCreated")
                == "LeaveApplicationCreated")

    def test_On사건Trigger동작_꼴(self):
        assert (policy_name_says("OnDeductionBasisCreatedTriggerGrantAnnualLeave")
                == "DeductionBasisCreated")

    def test_못_읽으면_None(self):
        """세지 않는다 — 조용히 틀린 판정을 내는 쪽이 더 나쁘다."""
        assert policy_name_says("SomePolicyWithoutTheKeyword") is None
        assert policy_name_says("") is None


class Test축약은_오배선이_아니다:
    def test_오늘_화면에_뜬_둘(self):
        """10-19 에 실제로 "아예 없습니다" 로 뜬 두 건."""
        for name in ("ExpireUnusedAnnualLeaveOnMonthlyAttendanceClosing",
                     "CreatePayrollIntegrationInterfaceOnMonthlyAttendanceClosing"):
            said = policy_name_says(name)
            assert said == "MonthlyAttendanceClosing"
            assert policy_name_is_abbrev(said, "MonthlyAttendanceClosingConfirmed")

    def test_반대_방향도_축약이다(self):
        """이름이 더 길 수도 있다 — 어느 쪽이 길든 앞부분이면 축약이다."""
        assert policy_name_is_abbrev("MonthlyAttendanceClosingConfirmed",
                                     "MonthlyAttendanceClosing")

    def test_낱말_중간에서_끊긴_것은_봐주지_않는다(self):
        """`MonthlyAttendanceClos` 는 축약이 아니다 — 낱말 경계가 아니다."""
        assert not policy_name_is_abbrev("MonthlyAttendanceClos",
                                         "MonthlyAttendanceClosing")

    def test_다른_사건은_그대로_오배선이다(self):
        """위험한 쪽 — 10-16 의 진짜 오배선(`…Confirmed` vs `…Finalized`)."""
        assert not policy_name_is_abbrev("AttendanceClosingConfirmed",
                                         "AttendanceClosingFinalized")
        assert not policy_name_is_abbrev("LeaveApplicationCreated",
                                         "MonthlyAttendanceClosingConfirmed")

    def test_빈_값은_축약이_아니다(self):
        assert not policy_name_is_abbrev("", "MonthlyAttendanceClosing")
        assert not policy_name_is_abbrev("MonthlyAttendanceClosing", "")
