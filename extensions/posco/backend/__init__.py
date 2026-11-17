# -*- coding: utf-8 -*-
"""POSCO 확장 — 백엔드 쪽. 지금 posco-web 판이 하는 것을 등록부 값으로 적는다.

⚠ P3 단계에서는 코어가 아직 이 자리들을 읽지 않는다(값만 들어간다). P5(포스코 옮기기)에서
  auth · llm · standard_items · exportDocument · code_templates 가 하나씩 읽기 시작하고,
  그때마다 posco-web 브랜치의 해당 코드를 지운다. 남은 목록: extensions/posco/README.md
"""

from __future__ import annotations


def register(app, registry) -> None:  # noqa: ARG001
    # 생성 모델 기본값 — posco-web `llm_model_choice.default_model()` 의 "gpt-4.1".
    # P-GPT 게이트웨이 주소·키는 코드가 아니라 프로필(.env 의 PGPT_*)이다.
    registry.llm_overrides["default_model"] = "gpt-4.1"

    # 산출물 정책 — 서비스설계서 파일 이름 틀 · DOCX 만 · ECM 검사.
    registry.deliverable_policies.update({
        "file_name_template": "설계_{project}_{kind}_{yyyyMMdd}_{HHmmss}",
        "allowed_formats": ["docx"],
        "ecm_check": True,
    })

    # 코드 템플릿 세트(고객 데이터) — posco-web scripts/fetch-templates.sh 의 핀.
    registry.template_sets.append({
        "name": "template-poscodx",
        "repo": "https://github.com/msa-ez/template-poscodx",
        "java_package_prefix": "com.poscodx",
    })

    # SWP SSO 주소 — 예전에는 코어 auth/config.py 의 기본값이었다(통합 P5 에서 여기로).
    # .env 의 SWP_* 가 비어 있을 때만 채운다. 현장 compose 는 이 셋을 `${SWP_SSO_…:-}` 로 비워 넘긴다.
    registry.env_defaults.update({
        "SWP_SSO_REDIRECT_URL": "http://swpsso.posco.net/idms/U61/jsp/redirect.jsp?redir_url=",
        "SWP_SSO_VALID_CHECK_URL": "http://swpsso.posco.net/idms/U61/jsp/isValidSSO.jsp",
        "SWP_SSO_LOGIN_URL": "http://swp.posco.net",
        "SWP_EMAIL_FALLBACK_DOMAIN": "posco.local",
    })

    # 표준항목 MCP(searchDataDictionary)의 필드 매핑은 `standard_items/mcp_provider.py` 에 있고
    # `ROBO_STANDARD_MCP_URL` 로 켜고 끈다(비면 꺼짐) — 다음 단계에서 standard_item_providers 로 옮긴다.
