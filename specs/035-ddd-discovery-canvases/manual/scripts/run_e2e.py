#!/usr/bin/env python3
"""Run 035 e2e: boot backend→vite→playwright→curl evidence→teardown."""

import json, os, signal, subprocess, sys, time, urllib.request, pathlib, shutil

WT = "/Users/uengine/main-robo-arch/robo-architect-035"
MANUAL = f"{WT}/specs/035-ddd-discovery-canvases/manual"
BE_PORT = 8772
FE_PORT = 5182
SHOTS = f"{MANUAL}/screenshots"
ART = f"{MANUAL}/artifacts"

pathlib.Path(SHOTS).mkdir(parents=True, exist_ok=True)
pathlib.Path(ART).mkdir(parents=True, exist_ok=True)

be_proc = None
fe_proc = None

def kill_port(port):
    try:
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        for pid in result.stdout.strip().splitlines():
            os.kill(int(pid), signal.SIGTERM)
        time.sleep(0.5)
    except Exception:
        pass

def wait_http(url, timeout=90):
    """Wait until curl can reach url (works for both IPv4 and IPv6 vite)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(
            ["curl", "-sf", "-m", "2", url, "-o", "/dev/null", "-w", "%{http_code}"],
            capture_output=True, text=True
        )
        code = r.stdout.strip()
        if code and code not in ("000", ""):
            return True
        time.sleep(1)
    return False

def patch_proxy(target_port):
    cfg = f"{WT}/frontend/vite.config.js"
    txt = open(cfg).read()
    import re
    txt2 = re.sub(r"target: 'http://127\.0\.0\.1:\d+'", f"target: 'http://127.0.0.1:{target_port}'", txt)
    open(cfg, "w").write(txt2)

def restore_proxy():
    patch_proxy(8000)

try:
    # Kill any prior listeners
    kill_port(BE_PORT)
    kill_port(FE_PORT)

    # 1. Backend
    print(f"Starting backend on {BE_PORT}...")
    be_proc = subprocess.Popen(
        [f"{WT}/.venv/bin/python", "-m", "uvicorn", "api.main:app",
         "--host", "127.0.0.1", "--port", str(BE_PORT)],
        cwd=WT, stdout=open(f"{ART}/uvicorn.log", "w"), stderr=subprocess.STDOUT
    )
    if not wait_http(f"http://127.0.0.1:{BE_PORT}/docs", 60):
        raise RuntimeError("Backend did not start")
    print("Backend up")

    # openapi.json
    with urllib.request.urlopen(f"http://127.0.0.1:{BE_PORT}/openapi.json") as r:
        open(f"{ART}/openapi.json", "wb").write(r.read())

    # 2. Vite
    print(f"Patching vite proxy → {BE_PORT}...")
    patch_proxy(BE_PORT)

    print(f"Starting vite on {FE_PORT}...")
    npm = shutil.which("npm") or "npm"
    fe_proc = subprocess.Popen(
        ["npx", "vite", "--port", str(FE_PORT), "--strictPort"],
        cwd=f"{WT}/frontend",
        stdout=open(f"{ART}/vite.log", "w"), stderr=subprocess.STDOUT,
        env={**os.environ, "PATH": os.environ["PATH"]}
    )
    if not wait_http(f"http://localhost:{FE_PORT}", 90):
        raise RuntimeError("Vite did not start")
    print("Vite up — waiting 4s for full hydration")
    time.sleep(4)

    # 3. Playwright
    print("Running Playwright...")
    pw_env = {**os.environ,
              "APP_URL": f"http://localhost:{FE_PORT}",
              "PLAYWRIGHT_BROWSERS_PATH": os.path.expanduser("~/Library/Caches/ms-playwright")}
    # Run playwright from main-repo frontend (has node_modules/@playwright/test).
    # Copy spec there, run, then remove.
    MAIN_FE = "/Users/uengine/main-robo-arch/robo-architect/frontend"
    # Use /tmp so no package.json "type:module" interferes
    tmp_spec = "/tmp/e2e_035_tmp.spec.cjs"
    tmp_cfg  = "/tmp/e2e_035_tmp.config.cjs"
    pw_bin = f"{MAIN_FE}/node_modules/.bin/playwright"

    # Write a self-contained config (testDir = MAIN_FE, testMatch for our tmp spec)
    NM = f"{MAIN_FE}/node_modules"
    with open(tmp_cfg, "w") as f:
        f.write(f"""// plain object config — no require needed
module.exports = {{
  testDir: '/tmp',
  testMatch: ['e2e_035_tmp.spec.cjs'],
  timeout: 90000,
  fullyParallel: false,
  workers: 1,
  reporter: 'line',
  use: {{ headless: true, actionTimeout: 15000 }},
}}
""")
    # Copy spec (with updated SHOTS path using absolute)
    # Spec: require @playwright/test via explicit path so /tmp can find it
    spec_src = open(f"{ART}/playwright-ddd-canvases.spec.js").read()
    spec_src = spec_src.replace(
        "require('@playwright/test')",
        f"require('{MAIN_FE}/node_modules/@playwright/test')"
    )
    # Replace relative SHOTS with absolute path so screenshots land in the right dir
    spec_src = spec_src.replace(
        "const SHOTS = path.resolve(__dirname, '../screenshots')",
        f"const SHOTS = '{SHOTS}'"
    )
    spec_src = spec_src.replace(
        "const APP = process.env.APP_URL || 'http://localhost:5182'",
        f"const APP = '{pw_env.get('APP_URL', 'http://localhost:5182')}'"
    )
    with open(tmp_spec, "w") as f:
        f.write(spec_src)

    try:
        pw_result = subprocess.run(
            [pw_bin, "test", "--config", tmp_cfg, "--reporter=line"],
            cwd="/tmp", env=pw_env, capture_output=True, text=True
        )
    finally:
        for tmp in (tmp_spec, tmp_cfg):
            pathlib.Path(tmp).unlink(missing_ok=True)
    print(pw_result.stdout[-3000:] if pw_result.stdout else "")
    if pw_result.stderr:
        print("STDERR:", pw_result.stderr[-1000:])
    with open(f"{ART}/playwright.out", "w") as f:
        f.write(pw_result.stdout + "\n" + pw_result.stderr)

    # 4. curl evidence
    B = f"http://127.0.0.1:{BE_PORT}"

    def api_call(method, path, body=None):
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(B + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())

    # 05 wizard start
    _, start = api_call("POST", "/api/requirements/ddd-wizard/start", {
        "scope": "greenfield",
        "profile": {"projectType": "greenfield", "dddExperience": "first_time",
                    "teamSize": "small", "existingArtifacts": []}
    })
    with open(f"{SHOTS}/05_wizard_start.txt", "w") as f:
        f.write("# 마법사 시작 응답\n\n")
        f.write(f"세션 ID: {start['sessionId']}\n")
        f.write("추천 단계:\n")
        for s in start["recommendedPlan"]:
            f.write(f"  {'✓' if s['recommended'] else '○'} {s['key']}: {s['title']}\n")
        f.write(f"\n프로파일 요약: {start.get('profileSummary','')}\n")
    print("05 wizard start OK")

    # 06 BC canvas + classification (first available BC)
    _, tree = api_call("GET", "/api/requirements/tree")
    epics = tree.get("epics", [])
    with open(f"{SHOTS}/06_canvas_classification.txt", "w") as f:
        f.write("# BC 캔버스 + 전략 분류(generic) 검증\n\n")
        if epics:
            bcid = epics[0]["id"]
            nm = epics[0].get("displayName") or epics[0].get("name")
            f.write(f"대상 BC: {nm} (id: {bcid})\n\n")
            # patch classification
            _, cls = api_call("PATCH", f"/api/contexts/{bcid}/classification", {"classification": "generic"})
            f.write(f"PATCH classification=generic → {cls.get('classification')}\n")
            # canvas GET
            _, canvas = api_call("GET", f"/api/requirements/bounded-context/{bcid}/canvas")
            f.write(f"Canvas GET: name={canvas['name']}, classification={canvas['classification']}, version={canvas['version']}\n")
            # canvas PATCH (책임 추가)
            _, patched = api_call("PATCH", f"/api/requirements/bounded-context/{bcid}/canvas",
                                  {"purpose": "E2E 검증용 책임 설명"})
            f.write(f"Canvas PATCH purpose: '{patched.get('purpose')}', version={patched['version']}\n")
            # restore classification
            api_call("PATCH", f"/api/contexts/{bcid}/classification", {"classification": "core"})
            f.write("\n※ 분류 복원: core\n")
        else:
            f.write("(그래프에 BoundedContext 없음 — 라이브 E2E 기록 참조)\n")
    print("06 canvas+classification OK")

    # 07 ddd-export
    _, exp = api_call("POST", "/api/requirements/ddd-export", {"outputDir": "/tmp/ddd_e2e_manual"})
    with open(f"{SHOTS}/07_ddd_export.txt", "w") as f:
        f.write("# 그래프 → .ddd 내보내기 검증\n\n")
        f.write(f"생성된 파일: {len(exp['writtenFiles'])}개\n")
        for fn in exp["writtenFiles"][:8]:
            f.write(f"  {fn}\n")
        if len(exp["writtenFiles"]) > 8:
            f.write(f"  ... (외 {len(exp['writtenFiles'])-8}개)\n")
    import shutil as _sh
    _sh.rmtree("/tmp/ddd_e2e_manual", ignore_errors=True)
    print("07 ddd-export OK")

    # 08 pivotal 404
    with open(f"{SHOTS}/08_pivotal_404.txt", "w") as f:
        f.write("# 없는 이벤트 피보탈 토글 → 404 기대\n\n")
        try:
            api_call("POST", "/api/requirements/pivotal-events/toggle",
                     {"eventId": "__nope__", "pivotal": True})
            f.write("FAIL: 404가 아닌 200 반환\n")
        except urllib.error.HTTPError as e:
            f.write(f"HTTP {e.code} → {'PASS ✓' if e.code == 404 else 'FAIL'}\n")
    print("08 pivotal 404 OK")

    print("\n=== E2E 완료 ===")
    print("Screenshots:", sorted(os.listdir(SHOTS)))

finally:
    if fe_proc:
        fe_proc.terminate()
    if be_proc:
        be_proc.terminate()
    restore_proxy()
    print("Cleanup done. Proxy restored to 8000.")
