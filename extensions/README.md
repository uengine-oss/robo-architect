# extensions/ — 고객 차이는 여기에만

robo-architect 는 **브랜치 하나(main)** 다. 고객·판은 브랜치가 아니라 빌드 입력이다.

```
extensions/
  _default/           고객 없음 = 지금 main 동작(빈 값)
    backend/__init__.py   register(app, registry) — 아무것도 안 넣는다
    frontend/index.js     export default { id: 'default' }
  posco/              POSCO — 남은 이전 목록은 posco/README.md
```

| 입력 | 어디서 | 효과 |
|---|---|---|
| `ROBO_CUSTOMER=<고객>` | API 기동 환경 | `api/extensions.py` 가 `extensions/<고객>/backend` 의 `register()` 를 불러 등록부를 채운다 |
| `VITE_CUSTOMER=<고객>` | web 빌드 | `@customer` → `extensions/<고객>/frontend/index.js` · 값은 `frontend/src/app/customer.js` 가 기본값과 합친다 |
| `VITE_EDITION=web\|desktop` | web 빌드 | `__ROBO_EDITION__` 상수 |

규칙
- 코어 코드에 고객 이름으로 분기(`if posco`)를 쓰지 않는다. 코어는 **등록부·`customer` 값만** 읽는다.
- 없는 고객을 고르면 빌드·기동이 멈춘다 — 기본 판으로 조용히 나가지 않게.
- 새 고객 = 이 폴더에 `<고객>/` 하나 + 프로필. 브랜치를 만들지 않는다.
- 기본 빌드에 고객 문자열이 새지 않는지 `node scripts/check-customer-leaks.mjs <dist>` 로 본다.
