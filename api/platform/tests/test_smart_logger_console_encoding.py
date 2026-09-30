# -*- coding: utf-8 -*-
"""**관측 수단이 관측 대상을 죽이지 못한다** — 콘솔 로그의 인코딩 사고.

2026-09-30 실측. 설치본이 한국어 Windows 에서 깨끗하게(셸 없이) 뜨면 번들 python
의 stdout 인코딩이 `cp949` 가 된다. `cp949` 에는 em dash(`—` U+2014)가 없다. 그래서

    print("[INFO][ingestion.hybrid.document_bpm] facade produced Phase 1 bundle — using it")

한 줄이 `UnicodeEncodeError` 를 호출자에게 던지고, 그것이 문서 업로드 인제스천을
**Phase 1 성공 직후** 매번 죽였다. 죽인 것은 로직이 아니라 성공을 알리는 INFO 였다.

정식 수정은 `desktop/src/main/backend.ts` 가 `PYTHONUTF8=1` 로 띄우는 것이고
(`desktop/tests/unit/backend-stdout-encoding.spec.ts` 가 그걸 잰다), 이 검사는 그
방어선이 뚫렸을 때를 잰다 — 운영자가 백엔드를 손으로 띄우는 경로가 남아 있다.
"""

import io

import pytest

from api.platform.observability.smart_logger import SmartLogger

EM_DASH_MESSAGE = "facade produced Phase 1 bundle — using it"


class Cp949Stdout(io.TextIOBase):
    """`cp949` 파이프에 붙은 stdout 을 흉내낸다 — 인코딩 불가 글자에서 던진다."""

    encoding = "cp949"

    def __init__(self) -> None:
        self.written: list[str] = []

    def write(self, s: str) -> int:  # type: ignore[override]
        s.encode("cp949")  # 여기서 UnicodeEncodeError
        self.written.append(s)
        return len(s)

    def flush(self) -> None:  # pragma: no cover - 호출만 받는다
        return None


def _logger() -> SmartLogger:
    return SmartLogger(
        main_log_path="",
        detail_log_dir="",
        min_level="INFO",
        include_all_min_level="ERROR",
        console_output=True,
        file_output=False,
    )


def test_cp949_stdout_은_로그를_던지지_않는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """이게 깨지면 인제스천이 성공 로그 한 줄에 죽는다."""
    fake = Cp949Stdout()
    monkeypatch.setattr("sys.stdout", fake)

    _logger()._log("INFO", EM_DASH_MESSAGE, category="ingestion.hybrid.document_bpm")

    assert fake.written, "로그를 완전히 삼켰다 — 대체 표기로라도 한 줄은 남아야 한다"
    joined = "".join(fake.written)
    assert "facade produced Phase 1 bundle" in joined
    assert "—" not in joined, "cp949 에 못 담는 글자가 그대로 남았다"


def test_다른_출력_오류도_호출자를_죽이지_않는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """Electron 종료 중 파이프가 닫히는 경우 — 로그를 잃는 편이 낫다."""

    class BrokenPipe(io.TextIOBase):
        encoding = "utf-8"

        def write(self, s: str) -> int:  # type: ignore[override]
            raise OSError(22, "Invalid argument")

    monkeypatch.setattr("sys.stdout", BrokenPipe())
    _logger()._log("INFO", "평범한 메시지", category="x")


def test_정상_stdout_은_그대로_찍는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """방어가 멀쩡한 경로를 바꿔 쓰지 않는지."""
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)

    _logger()._log("INFO", EM_DASH_MESSAGE, category="c")

    assert out.getvalue() == f"[INFO][c] {EM_DASH_MESSAGE}\n"
