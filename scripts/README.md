# Architect 실행·빌드 스크립트

Windows에서는 `.cmd` 진입점을 사용합니다. 두 진입점은 중복된 서비스 로직을
갖지 않고, 같은 디렉터리 구조의 `robo-workspace` 공통 실행기를 호출합니다.

## Electron 개발 실행

```cmd
scripts\dev-desktop.cmd
scripts\dev-desktop.cmd -SkipBuild
scripts\dev-desktop.cmd -NoElectron
scripts\dev-desktop.cmd -Stop
```

- 기본: host와 Analyzer remote를 co-locate해 unpacked 앱을 빌드한 뒤 공통 백엔드와 해당 앱 실행
- `-SkipBuild`: 기존 `frontend/dist` 재사용
- `-NoElectron`: 공통 백엔드만 실행
- `-Stop`: 이 프로필이 기록한 프로세스 트리만 종료

기존 스크립트와 달리 중첩 `robo-analyzer` 체크아웃을 실행하지 않고, 독립된
형제 저장소를 사용합니다. data-fabric/parser의 로컬 포트는 Windows 예약 포트
충돌을 피하기 위해 8404/8401이며 Gateway에 실제 URL이 전달됩니다.

## Electron 패키징

```cmd
scripts\build-desktop-app.cmd
scripts\build-desktop-app.cmd -Installer
scripts\build-desktop-app.cmd -SkipFrontend
```

- 기본 결과: `desktop\out\dist\win-unpacked\Robo-Architect.exe`
- `-Installer`: `desktop\out\dist\Robo-Architect-Setup-<version>.exe`
- `-SkipFrontend`: 기존 co-locate 결과를 재사용

현재 산출물은 Python 백엔드 런타임을 포함하지 않는 개발 패키지입니다. 독립
설치본 배포는 런타임 번들 작업 이후에 지원해야 합니다.

## 최초 준비와 경로

먼저 `robo-workspace`에서 다음을 한 번 실행합니다.

```cmd
robo.cmd setup architect-electron
robo.cmd doctor architect-electron
```

기본 배치는 `robo-workspace`와 `project/robo-architect`가 같은 상위 디렉터리
아래에 있는 구조입니다. 다른 위치라면 `ROBO_WORKSPACE_DIR`을 지정하십시오.

나머지 `check_robo_spec_install.sh`, `generate_oda_manual.py`,
`seed_oda_demo.py`는 별도 목적의 도구이며 이 실행 배선과 무관합니다.
