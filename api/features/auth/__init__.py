"""기업 인증(SSO) — provider 전략.

`AUTH_PROVIDER` 로 전환한다. 기본값 `none` 은 기존 동작(`X-User-*` 헤더 기반
Actor 전파)을 그대로 유지하므로, 설정하지 않으면 아무것도 바뀌지 않는다.
"""

from api.features.auth.config import AuthProvider, SwpSettings, auth_provider

__all__ = ["AuthProvider", "SwpSettings", "auth_provider"]
