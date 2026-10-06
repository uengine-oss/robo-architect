"""템플릿 기반 코드 생성 — 읽기, 그리고 **관리자의 수정**(TPL-1).

템플릿은 산출물의 파일이 **원본**이고, 고친 것은 중앙 DB 에 쌓인다(`store.py`).
한 줄을 고치려고 전체를 다시 굽고 20여 대에 재설치하던 비용이 이것으로 없어진다.
**고치는 것은 관리자만** — 템플릿의 `<function>` 블록은 렌더러가 `new Function` 으로
실제로 실행하는 JavaScript 라, 쓰기 권한은 곧 코드 실행 권한이다.

렌더링 자체는 프런트엔드가 한다. **템플릿이 자기 Handlebars 헬퍼를
JavaScript 로 들고 다니기 때문**이다(`<function>` 블록). 파이썬으로 옮기려면
그 JS 를 실행해야 하므로, 렌더러는 브라우저에 두고 서버는 재료만 준다 —
템플릿 원문과 ES 모델 컨텍스트.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query
from starlette.requests import Request

from api.features.accounts.guard import require_admin
from api.features.code_templates import context as ctx_builder
from api.features.code_templates import repository
from api.features.code_templates import store
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/code-templates", tags=["code-templates"])


def _empty_hint() -> str:
    """세트가 0개일 때의 안내. **읽는 사람이 다르다.**

    개발 중이면 `fetch-templates.sh` 를 돌리면 된다. 그런데 **납품본에서는 그
    안내가 쓸모없다** — 사내망에는 GitHub 도 없고, 받는 쪽이 할 수 있는 일도
    아니다. 그쪽에는 "덜 구워진 산출물" 이라고 말해야 전달이 된다.

    설치본인지는 `app` 폴더 이름으로 보지 않는다. 굽기가 번들 런타임에만
    넣는 표식(`ROBO_PACKAGED_RUNTIME`)이 있으면 그것을 쓰고, 없으면 개발로 본다.
    """
    import os

    packaged = (os.environ.get("ROBO_PACKAGED_RUNTIME") or "").strip().lower() in (
        "1", "true", "yes", "on")
    if packaged:
        return (
            "코드 생성 템플릿이 설치본에 들어 있지 않습니다. 이 PC 에서 고칠 수 "
            "없고, 템플릿을 포함해 다시 구운 설치본이 필요합니다 — 배포 담당자에게 "
            "알려 주세요."
        )
    return "scripts/fetch-templates.sh 를 실행해 템플릿을 받으세요."


@router.get("/sets")
async def list_sets() -> dict:
    """`templates/` 아래에 받아 둔 템플릿 묶음 목록."""
    sets = repository.list_template_sets()
    # 몇 장이 원본과 다른가. 화면이 "손댄 묶음" 을 알아볼 수 있어야 한다.
    # 질의는 한 번이다 — 묶음마다 물으면 접속이 묶음 수만큼 열린다.
    counts = store.override_counts()
    for item in sets:
        item["overridden"] = counts.get(item["name"], 0)
    return {
        "sets": sets,
        # 비어 있으면 화면이 원인을 말할 수 있어야 한다.
        "templatesRoot": str(repository.TEMPLATES_ROOT),
        "hint": None if sets else _empty_hint(),
    }


@router.get("/sets/{set_name}/files")
async def list_files(request: Request, set_name: str) -> dict:
    """묶음 하나의 템플릿 전체 — front matter 를 떼고 본문과 헬퍼를 나눠서."""
    overrides = store.overrides(set_name)
    try:
        templates = repository.load_templates(set_name, overrides)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    files = [t.to_dict() for t in templates]
    # 설정 파일은 생성물이 아니다 — 렌더 대상에서 뺀다.
    renderable = [f for f in files if f["forEach"] and not f["isConfiguration"]]
    SmartLogger.log(
        "INFO",
        f"Template set loaded: {set_name}",
        category="code_templates.files",
        params={**http_context(request), "set": set_name,
                "files": len(files), "renderable": len(renderable)},
    )
    return {
        "set": set_name,
        "files": files,
        # 이 묶음이 요구하는 생성 옵션. `_template/` 의 설정 파일이 선언한다.
        "options": repository.config_fields_for(set_name, overrides),
        "summary": {
            "files": len(files),
            "renderable": len(renderable),
            "configuration": sum(1 for f in files if f["isConfiguration"]),
            "withHelpers": sum(1 for f in files if f["functions"]),
            # 원본과 다른 장수. 0 이면 출고 상태 그대로다.
            "overridden": sum(1 for f in files if f["source"] == "db"),
        },
    }


@router.get("/sets/{set_name}/file")
async def get_file(
    request: Request,
    set_name: str,
    path: str = Query(..., min_length=1),
    version: int | None = Query(default=None),
) -> dict:
    """템플릿 한 장의 **원문**. 원본과 지금을 같이 준다.

    고친 적이 없으면 `current` 와 `original` 이 같다. `version` 을 주면 그 이력
    판의 본문을 `current` 자리에 넣는다 — 되돌리기 전에 눈으로 보라고.
    """
    try:
        original = repository.read_original(set_name, path)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    row = store.get(set_name, path)
    if original is None and row is None:
        raise HTTPException(status_code=404, detail=f"템플릿을 찾을 수 없습니다: {path}")
    current = row["body"] if row else original
    if version is not None:
        body = store.history_body(set_name, path, version)
        if body is None:
            raise HTTPException(status_code=404, detail="그 이력 판이 없습니다.")
        current = body
    updated = (row or {}).get("updated_at")
    # **출고 원본이 그 뒤에 바뀌었는가.** 고칠 때의 지문과 지금 산출물의 지문을
    # 견준다. 다르면 이 행이 **새 원본을 덮고 있는 것**이고, 사람은 그 사실을 알
    # 길이 없다 — 다음 설치본이 고친 템플릿이 조용히 묻히는 자리다.
    saved_sha = (row or {}).get("original_sha")
    original_changed = bool(
        saved_sha and original is not None
        and store.original_fingerprint(original) != saved_sha
    )
    return {
        "set": set_name,
        "path": path,
        # 산출물에 실려 온 그대로. DB 에만 있는 템플릿이면 없다.
        "original": original,
        "current": current,
        "source": "db" if row else "file",
        "modified": bool(row) and (original is None or row["body"] != original),
        "updatedAt": updated.isoformat() if hasattr(updated, "isoformat") else None,
        "updatedBy": (row or {}).get("updated_by"),
        "history": store.history(set_name, path),
        "originalChanged": original_changed,
        # 이 글이 **실행되는가**. 화면이 경고를 띄울 근거다.
        "hasFunctions": "<function>" in (current or ""),
    }


@router.put("/sets/{set_name}/file")
async def save_file(
    request: Request,
    set_name: str,
    path: str = Body(..., embed=True),
    body: str = Body(..., embed=True),
) -> dict:
    """템플릿 한 장을 고친다. **관리자만.**

    고친 내용은 중앙 DB 에 쌓이고 모든 PC 가 다음 조회부터 그것을 쓴다 —
    다시 굽지 않는다. `<function>` 블록은 렌더러가 실행하는 JavaScript 이므로
    여기에 쓰는 것은 **앱 안에서 코드를 돌리는 것**과 같다. 그래서 관리자만이고,
    저장마다 이력과 로그가 남는다.
    """
    uid = require_admin(request)
    try:
        # 묶음 이름과 경로가 템플릿 밖을 가리키지 않는지 먼저 본다.
        repository.read_original(set_name, path)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not (body or "").strip():
        raise HTTPException(status_code=400, detail="빈 템플릿은 저장하지 않습니다.")
    # 고칠 때의 출고 원본을 **지문으로** 남긴다 — 나중에 산출물이 바뀌면 그것을 안다.
    original = repository.read_original(set_name, path)
    saved = store.save(set_name, path, body, uid, original=original)
    SmartLogger.log(
        "WARN", "코드 생성 템플릿 수정",
        category="code_templates.saved",
        params={**http_context(request), "set": set_name, "path": path, "uid": uid,
                "bytes": saved["bytes"]},
    )
    return {"saved": True, **saved}


@router.delete("/sets/{set_name}/file")
async def revert_file(
    request: Request,
    set_name: str,
    path: str = Query(..., min_length=1),
) -> dict:
    """고친 것을 버리고 **산출물 원본으로 되돌린다.** 관리자만.

    원본을 복사해 두지 않으므로 되돌리기는 DB 행을 지우는 것이다 — 원본은 언제나
    산출물 안에 그대로 있다.
    """
    uid = require_admin(request)
    try:
        original = repository.read_original(set_name, path)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if original is None:
        # DB 에만 있던 템플릿이다. 되돌릴 원본이 없으니 지우는 것이 곧 삭제다.
        removed = store.revert(set_name, path, uid)
        return {"reverted": removed, "deleted": removed, "hasOriginal": False}
    removed = store.revert(set_name, path, uid)
    return {"reverted": removed, "deleted": False, "hasOriginal": True}


@router.get("/context")
async def get_context(
    request: Request,
    sessionId: str = Query(..., min_length=1),
    serviceId: str = Query(..., min_length=1),
) -> dict:
    """세션의 ES 모델을 렌더 컨텍스트로 편다.

    `serviceId` 는 자바 패키지의 한 마디가 되므로(`com.poscodx.<serviceId>.…`)
    호출자가 정한다. 화면은 세션 이름을 기본값으로 보여 주고 사용자가 고치게
    한다 — 여기서 추측하지 않는다.
    """
    payload = ctx_builder.build_context(sessionId, service_id=serviceId)
    if not payload["boundedContexts"]:
        raise HTTPException(
            status_code=404,
            detail=f"세션 '{sessionId}' 에 Bounded Context 가 없습니다. 이벤트 스토밍 승격이 끝났는지 확인하세요.",
        )
    SmartLogger.log(
        "INFO",
        "Template render context built.",
        category="code_templates.context",
        params={**http_context(request), "session_id": sessionId, "service_id": serviceId,
                "bounded_contexts": len(payload["boundedContexts"]),
                "aggregates": sum(len(b["aggregates"]) for b in payload["boundedContexts"])},
    )
    return payload
