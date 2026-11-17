"""프로젝트 라우트.

```
GET    /api/projects                    내가 접근할 수 있는 것만
POST   /api/projects                    graph 생성 + 소유자 권한
POST   /api/projects/adopt              이미 있는 graph 를 등록 (전환 전 데이터)
GET    /api/projects/{graph}/members    참여자
POST   /api/projects/{graph}/members    초대
DELETE /api/projects/{graph}/members/{uid}  회수
DELETE /api/projects/{graph}?confirm=<이름>   프로젝트 삭제(소유자만 · 데이터가 함께 사라진다)
```

**모든 경로가 신원을 요구한다.** 소유자 없는 프로젝트가 생기면 아무도 관리할 수
없고, 목록은 "내 것"이 정의되지 않으면 의미가 없다. 인증 강제(`AUTH_ENFORCE`)가
꺼져 있어도 여기서는 토큰을 요구한다 — 강제 스위치는 *다른 기능*을 열어 두기
위한 것이지 프로젝트 소유권을 흐리려는 것이 아니다.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Request

from api.features.auth.tokens import TokenError, verify_token
from api.features.projects import store
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _uid(request: Request) -> str:
    """요청자의 사번. 없으면 401.

    미들웨어가 이미 확인해 둔 클레임이 있으면 그걸 쓰고, 강제가 꺼져 있어 클레임이
    없으면 헤더를 직접 본다.
    """
    claims = getattr(request.state, "auth_claims", None)
    if not claims:
        header = request.headers.get("authorization") or ""
        token = header[7:].strip() if header[:7].lower() == "bearer " else None
        try:
            claims = verify_token(token)
        except TokenError:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    uid = str(claims.get("sub") or "")
    if not uid:
        raise HTTPException(status_code=401, detail="사용자를 알 수 없습니다.")
    return uid


def _require_admin(uid: str, graph: str) -> None:
    """공유를 바꾸려면 그 프로젝트의 admin 이어야 한다."""
    if store.level_of(uid, graph) != "admin":
        raise HTTPException(status_code=403, detail="이 프로젝트를 관리할 권한이 없습니다.")


def _guard(fn, *args, **kwargs):
    """저장소 오류를 사용자에게 전할 수 있는 형태로 바꾼다."""
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"저장소 오류: {str(exc)[:200]}")


@router.get("")
async def list_projects(request: Request) -> dict:
    uid = _uid(request)
    store.ensure_schema()
    return {"projects": _guard(store.list_projects, uid)}


@router.post("")
async def create_project(request: Request, body: dict = Body(...)) -> dict:
    uid = _uid(request)
    store.ensure_schema()
    payload = body or {}
    # 서비스 ID 는 만들 때 받지 않는다(2026-11-17 입력 제거). 본문에 와도 무시한다.
    project = _guard(store.create_project, payload.get("name", ""), uid)
    SmartLogger.log(
        "INFO", "프로젝트를 만들었다.",
        category="projects.created",
        params={**http_context(request), "graph": project["graph"], "owner": uid},
    )
    return project


@router.post("/adopt")
async def adopt(request: Request, body: dict = Body(...)) -> dict:
    """이미 있는 graph 를 프로젝트로 올린다. 전환 전 데이터를 목록에 넣는 길이다."""
    uid = _uid(request)
    store.ensure_schema()
    payload = body or {}
    project = _guard(store.adopt_graph, payload.get("graph", ""), payload.get("name", ""), uid,
                     payload.get("analyzerGraph") or None)
    SmartLogger.log(
        "INFO", "기존 graph 를 프로젝트로 등록했다.",
        category="projects.adopted",
        params={**http_context(request), "graph": project["graph"], "owner": uid},
    )
    return project


@router.get("/{graph}/analyzer-options")
async def get_analyzer_options(request: Request, graph: str) -> dict:
    """이 프로젝트가 고를 수 있는 분석 결과 목록.

    화면이 graph 이름을 타이핑시키지 않게 하려는 것이다. 목록은 **내가 접근할 수
    있는 것**으로 좁힌다 — 전체를 열면 남의 프로젝트 이름이 샌다.
    """
    uid = _uid(request)
    if store.level_of(uid, graph) is None:
        raise HTTPException(status_code=403, detail="이 프로젝트에 접근할 수 없습니다.")
    return {"options": _guard(store.analyzer_options, uid, graph)}


@router.post("/{graph}/analyzer")
async def set_analyzer(request: Request, graph: str, body: dict = Body(...)) -> dict:
    """이 프로젝트가 함께 볼 분석 graph 를 정한다.

    설계는 분석에서 뽑은 룰을 승격시킨 것이라 둘은 한 세트다. 따로 고르면 추적성이
    다른 분석을 가리키는데, 화면에는 결과가 나오므로 오류로 드러나지 않는다.
    """
    uid = _uid(request)
    _require_admin(uid, graph)
    result = _guard(store.set_analyzer_graph, graph, (body or {}).get("analyzerGraph") or None)
    SmartLogger.log(
        "INFO", "프로젝트의 분석 graph 를 정했다.",
        category="projects.analyzer_set",
        params={**http_context(request), "graph": graph, "by": uid,
                "analyzer": result.get("analyzerGraph")},
    )
    return result


@router.get("/{graph}/members")
async def get_members(request: Request, graph: str) -> dict:
    uid = _uid(request)
    if store.level_of(uid, graph) is None:
        raise HTTPException(status_code=403, detail="이 프로젝트에 접근할 수 없습니다.")
    return {"members": _guard(store.members, graph)}


@router.post("/{graph}/members")
async def add_member(request: Request, graph: str, body: dict = Body(...)) -> dict:
    uid = _uid(request)
    _require_admin(uid, graph)
    payload = body or {}
    level = payload.get("level") or "read"
    level = store.LEVEL_BY_ROLE_NAME.get(str(level).upper(), level)
    result = _guard(store.share, graph, str(payload.get("uid") or ""), level)
    SmartLogger.log(
        "INFO", "프로젝트를 공유했다.",
        category="projects.shared",
        params={**http_context(request), "graph": graph, "by": uid,
                "to": result["uid"], "level": result["level"]},
    )
    return result


@router.delete("/{graph}/members/{member_uid}")
async def remove_member(request: Request, graph: str, member_uid: str) -> dict:
    uid = _uid(request)
    _require_admin(uid, graph)
    result = _guard(store.unshare, graph, member_uid)
    SmartLogger.log(
        "INFO", "프로젝트 공유를 회수했다.",
        category="projects.unshared",
        params={**http_context(request), "graph": graph, "by": uid, "from": member_uid},
    )
    return result


@router.delete("/{graph}")
async def delete_project(request: Request, graph: str, confirm: str = "") -> dict:
    """프로젝트를 지운다 — **설계 graph 와 짝인 분석 graph 의 데이터가 함께 사라진다.**

    만든 사람(소유자)만 지운다. 관리 등급으로 공유받은 사람은 못 지운다 — 남이 만든 것을
    통째로 없애는 길을 공유 하나로 열지 않는다. 실수를 막으려고 `confirm` 에 **프로젝트
    이름 그대로**를 받는다(화면이 사람에게 그 이름을 다시 치게 한다).

    ⓘ posco-web: `/api/projects/**` 는 authority(납품판 이미지)로 넘어가는데 그 판에는 이 경로가
    없다 — `AuthorityProxyMiddleware` 가 이 한 경로만 넘기지 않고 여기서 처리한다. 이 프로세스는
    DB 소유자 자격(OG_PG_*)으로 붙으므로 `drop_project` 를 그대로 부를 수 있다.
    """
    uid = _uid(request)
    project = _guard(store.get_project, graph)
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    if str(project.get("ownerUid") or "") != uid:
        raise HTTPException(status_code=403, detail="프로젝트를 만든 사람만 지울 수 있습니다.")
    name = (project.get("displayName") or graph).strip()
    if (confirm or "").strip() != name:
        raise HTTPException(status_code=400, detail="확인용 이름이 프로젝트 이름과 다릅니다.")
    _guard(store.drop_project, graph)
    SmartLogger.log(
        # 되돌릴 수 없는 일이라 기본 최소 수준(ERROR)에서도 남게 한다.
        "ERROR", "프로젝트를 지웠다.",
        category="projects.deleted",
        params={**http_context(request), "graph": graph, "name": name, "by": uid,
                "analyzerGraph": project.get("analyzerGraph")},
    )
    return {"deleted": graph, "name": name}
