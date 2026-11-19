# Shared by build-packaged-runtime.sh (macOS) and build-packaged-runtime-win.sh (Windows x64, built on
# a Mac) — sourced, not run: the application snapshot, and compose.yml, the service settings and
# runtime-manifest.json, which are the same on both systems apart from the images and the interpreter.

say() { printf '\033[36m[runtime]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[runtime]\033[0m %s\n' "$*" >&2; exit 1; }

# api/ + skills/ + pyproject.toml + uv.lock (no tests, caches, logs)
#   copy_app_snapshot <repo root> <architect/app>
copy_app_snapshot() {
  local root=$1 app=$2 dir
  for dir in api skills; do
    rsync -a --delete \
      --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'tests' --exclude 'logs' \
      --exclude '*.pyc' --exclude '*.pyo' --exclude '.DS_Store' \
      "$root/$dir/" "$app/$dir/"
  done
  cp "$root/pyproject.toml" "$root/uv.lock" "$app/"
}

# compose.yml, config/*.env, architect/app/.env and runtime-manifest.json
#   write_runtime_files --root <repo> --out <runtime> --version <v> --registry <r> --source-tag <t>
#                       --python <interpreter, relative to the runtime> [--digests <file>]
#                       [--image-tag <tag>] [--context <docker context>] [--arch <amd64|arm64>]
#                       [--check-images | --no-images]
#   --image-tag     the release references' tag (default: the version)
#   --context       read the local images through this docker context (default: the current one)
#   --arch          refuse local images of another architecture
#   --check-images  only check that the local images are there, write nothing
#   --no-images     write compose.yml and the settings but no manifest (the images are not built yet)
write_runtime_files() {
  python3 - "$@" <<'PY'
import argparse, hashlib, json, os, shutil, subprocess, sys, urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
for opt in ("--root", "--out", "--version", "--registry", "--source-tag", "--python"):
    ap.add_argument(opt, required=True)
ap.add_argument("--digests", default="")
ap.add_argument("--image-tag", default="")
ap.add_argument("--context", default="")
ap.add_argument("--arch", default="")
ap.add_argument("--check-images", action="store_true")
ap.add_argument("--no-images", action="store_true")
args = ap.parse_args()
root, out, version, registry, source_tag = Path(args.root), Path(args.out), args.version, args.registry, args.source_tag
digests_file, image_tag = args.digests, args.image_tag or args.version
docker = ["docker"] + (["--context", args.context] if args.context else [])

# manifest key → (local image it is pushed from, release component name)
IMAGES = {
    "graphDb":   ("uengine/ontological-db",    "graph-db"),
    "graphBolt": ("uengine/ontological-bolt",  "graph-bolt"),
    "analyzer":  ("uengine/robo-analyzer",     "analyzer"),
    "catalog":   ("uengine/robo-data-catalog", "catalog"),
    "fabric":    ("uengine/robo-data-fabric",  "fabric"),
    "parser":    ("uengine/robo-antlr-parser", "parser"),
    "gateway":   ("uengine/robo-api-gateway",  "gateway"),
    # open-pencil 렌더러. 없으면 와이어프레임 단계가 **조용히** 빈다(compose 의 주석에 실측).
    "wireframe": ("uengine/open-pencil",        "wireframe"),
}

# Public images the release references as they are — not rebuilt, not re-pushed under
# robo-architect-lite-*. Their identity (platform manifest digest · config digest · size) is read
# from the registry anonymously, the way the app will pull them.
#
# pdf2bpmn: 문서→BPMN. main 개발 스펙(deploy/pdf2bpmn-selfhosted/compose.yml)과 같은 컨테이너 하나 —
# 추출기 이미지 위에 facade.py 를 얹고, 백엔드가 PDF2BPMN_FACADE_URL 로 부른다. 핀은 main 의
# runtime-manifest.template.json 과 같다(e618977). amd64 전용 — Apple Silicon 에서는 에뮬레이션으로 돈다.
EXTERNAL_IMAGES = {
    "pdf2bpmn": ("ghcr.io/uengine-oss/process-gpt-bpmn-extractor:19ea082", "amd64"),
}

# Per-service settings (the same values as the development runtime, robo-lite-src/build/make-runtime.py).
# The analyzer's LLM is the user's Claude Code through the host API (/api/llm-bridge/v1), embeddings
# off (no semantic search). Secrets appear as bare names: compose passes the launching
# environment's value, and a packaged app has none.
ENV = {
    "analyzer": """ROBO_LLM_CONFIG=claude_code_bridge
ROBO_LLM_API_KEY=claude-code-bridge
ROBO_LLM_REPETITION_GUARD=true
ROBO_LLM_RESPONSE_CACHE=true
ROBO_LLM_RESPONSE_CACHE_REQUIRE_HIT=false
ROBO_BUDGET_RUN_USD=20
ROBO_PIPELINE_MAX_CONCURRENCY=16
ROBO_PIPELINE_LLM_MAX_CONCURRENCY=4
ROBO_PIPELINE_BATCH_MAX_TOKENS=1500
ROBO_PIPELINE_EMBED_ENABLED=false
ROBO_CATALOG_ENABLED=true
ROBO_CATALOG_TIMEOUT_SECONDS=120
ROBO_NEO4J_RETRY_MAX_ATTEMPTS=5
ROBO_NEO4J_RETRY_BACKOFF_SECONDS=2
ROBO_RUNTIME_EVENT_FILE_ENABLED=true
ROBO_RUNTIME_EVENT_LEVEL=INFO
ROBO_RUN_OUTPUT_DIR=/data/logs
ROBO_EMBED_PROVIDER=openai
ROBO_EMBED_MODEL=text-embedding-3-small
ROBO_EMBED_API_BASE=https://api.openai.com/v1
ROBO_EMBED_API_KEY
ROBO_SEARCH_LLM_CONFIG=claude_code_bridge
ROBO_SEARCH_LLM_API_KEY=claude-code-bridge
""",
    "catalog": """LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY
OPENAI_API_KEY
EMBEDDING_MODEL=text-embedding-3-small
FK_INFERENCE_ENABLED=true
FK_SAMPLE_SIZE=25
FK_SIMILARITY_THRESHOLD=0.8
FK_MATCH_RATIO_THRESHOLD=0.8
FK_CONCURRENCY=5
METADATA_TIMEOUT_CONNECT=5
METADATA_TIMEOUT_REQUEST=30
""",
    "fabric": """DATA_FABRIC_QUERY_TIMEOUT_SECONDS=30
OPENAI_API_KEY
ROBO_DATASOURCE_REPLACE_LOCALHOST=host.docker.internal
""",
    "parser": """PARSER_REPAIR_APPLY_TO_SOURCE=false
PARSER_REPAIR_AGENT_ENABLED=false
""",
    "gateway": "",
    # main 개발 스펙과 같다: OpenAI · gpt-4o · facade 공유키 없음(루프백 바인딩).
    # OPENAI_BASE_URL 은 기본 주소 그대로지만 적어 둔다 — 앱의 pdf2bpmn 기능 프로브가 이 값으로
    # 키를 값싸게 확인한다(없으면 "못 잼"). 키는 굽지 않는다(이름만 — compose 가 호스트 값을 넘긴다).
    "pdf2bpmn": """OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY
LLM_MODEL=gpt-4o
OPENAI_MODEL=gpt-4o
""",
}

# The analyzer checks a sealed capability file for its LLM before every run (run_executor preflight)
# and refuses the run when the two values are missing — with the claude_code_bridge config above,
# every legacy analysis would stop before it starts. The file ships in the analyzer image; its hash
# is read from the submodule the image is built from, so the two cannot drift apart.
CAPABILITIES_REF = "llm/capabilities/claude_code_bridge.yaml"
_capabilities = root / "robo-analyzer" / "robo-data-analyzer" / CAPABILITIES_REF
if not _capabilities.is_file():
    raise SystemExit(f"[runtime] no {_capabilities} — the analyzer submodule is missing or too old")
ENV["analyzer"] += (f"ROBO_LLM_MODEL_RUNTIME_CAPABILITIES_REF={CAPABILITIES_REF}\n"
                    f"ROBO_LLM_MODEL_RUNTIME_CAPABILITIES_SHA256={hashlib.sha256(_capabilities.read_bytes()).hexdigest()}\n")

# The host Architect API's settings (api/main.py load_dotenv). Proposals, plans and implementation
# run as skills through the local Claude Code CLI; Neo4j/Bolt settings come from the app at start.
ARCHITECT_ENV = """# Robo Architect Lite — host Architect API settings (no secrets).
SKILL_RUNNER_PROVIDER=claude_cli
LLM_PROVIDER=openai
"""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def head(path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "0" * 40


def inspect(ref: str, fmt: str) -> str:
    return subprocess.check_output(docker + ["image", "inspect", ref, "--format", fmt], text=True,
                                   stderr=subprocess.DEVNULL).strip()


def image_id(ref: str) -> str:
    try:
        found = inspect(ref, "{{.Id}}" + ("|{{.Os}}/{{.Architecture}}" if args.arch else ""))
    except subprocess.CalledProcessError:
        raise SystemExit(f"[runtime] the local image {ref} is missing — build it first")
    found, _, platform = found.partition("|")
    if args.arch and platform != f"linux/{args.arch}":
        raise SystemExit(f"[runtime] the local image {ref} is {platform}, not linux/{args.arch}")
    return found


def image_size(ref: str) -> int:
    return int(inspect(ref, "{{.Size}}"))


def registry_identity(ref: str, arch: str) -> tuple[str, str, int]:
    """(platform manifest digest, config digest, download size) of a public ghcr image, anonymously."""
    name, _, tag = ref.removeprefix("ghcr.io/").rpartition(":")
    accept = ", ".join([
        "application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"])
    with urllib.request.urlopen(f"https://ghcr.io/token?scope=repository:{name}:pull", timeout=30) as r:
        token = json.load(r)["token"]

    def get(reference: str) -> tuple[dict, str]:
        req = urllib.request.Request(f"https://ghcr.io/v2/{name}/manifests/{reference}",
                                     headers={"Authorization": f"Bearer {token}", "Accept": accept})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r), r.headers["Docker-Content-Digest"]

    top, digest = get(tag)
    if "manifests" in top:
        entry = next((m for m in top["manifests"]
                      if m.get("platform", {}).get("os") == "linux" and m["platform"].get("architecture") == arch), None)
        if entry is None:
            raise SystemExit(f"[runtime] {ref} has no linux/{arch} image")
        top, digest = get(entry["digest"])
    return digest, top["config"]["digest"], top["config"]["size"] + sum(l["size"] for l in top["layers"])


if args.check_images:
    for local, _ in IMAGES.values():
        image_id(f"{local}:{source_tag}")
    raise SystemExit(0)

shutil.copyfile(root / "desktop" / "runtime" / "compose.yml", out / "compose.yml")
# lite 프로필의 overlay — 앱이 lite 로 돌 때 모든 compose 호출에 얹는다(docker-stack.ts composeArgs).
shutil.copyfile(root / "desktop" / "runtime" / "compose.lite.yml", out / "compose.lite.yml")
# compose.yml 의 pdf2bpmn 이 마운트하는 facade — main 개발 스펙과 같은 파일 한 벌.
(out / "pdf2bpmn").mkdir(parents=True, exist_ok=True)
shutil.copyfile(root / "desktop" / "runtime" / "pdf2bpmn" / "facade.py", out / "pdf2bpmn" / "facade.py")
for name, text in ENV.items():
    (out / "config" / f"{name}.env").write_text(text, encoding="utf-8")
(out / "architect" / "app" / ".env").write_text(ARCHITECT_ENV, encoding="utf-8")
if args.no_images:
    (out / "runtime-manifest.json").unlink(missing_ok=True)
    print("[runtime] no manifest yet (--no-images) — the app cannot start from this runtime")
    raise SystemExit(0)

pushed = {}
if digests_file:
    pushed = json.loads(Path(digests_file).read_text(encoding="utf-8"))

images, ids, digests, sizes = {}, {}, {}, {}
for key, (local, component) in IMAGES.items():
    ref = f"{registry}/robo-architect-lite-{component}:{image_tag}"
    images[key] = ref
    ids[key] = image_id(f"{local}:{source_tag}")
    entry = pushed.get(key)
    if entry:
        if entry.get("ref") != ref:
            raise SystemExit(f"[runtime] {digests_file}: {key} was pushed as {entry.get('ref')}, not {ref}")
        if entry.get("id") != ids[key]:
            raise SystemExit(f"[runtime] {key}: {local}:{source_tag} is {ids[key]} but {entry.get('id')} was pushed — push again")
        digests[key] = entry["digest"]
        sizes[key] = int(entry["size"])
    else:
        sizes[key] = image_size(f"{local}:{source_tag}")
for key, (ref, arch) in EXTERNAL_IMAGES.items():
    images[key] = ref
    digests[key], ids[key], sizes[key] = registry_identity(ref, arch)

# Checkouts of the repositories that are not submodules here, at the commits the images came from.
lite_src = Path(os.environ.get("ROBO_LITE_SRC", "/Users/uengine/robo-lite-src"))
if digests_file:
    # A release must say what it was built from: head() answers forty zeros for a missing checkout.
    for repo in ("ontological-db", "antlr-code-parser", "api-gateway"):
        if head(lite_src / repo) == "0" * 40:
            raise SystemExit(f"[runtime] no git checkout at {lite_src / repo} — set ROBO_LITE_SRC")
environment = {k: {"file": f"config/{k}.env", "sha256": sha(out / "config" / f"{k}.env")} for k in ENV}
environment["architect"] = {"file": "architect/app/.env", "sha256": sha(out / "architect" / "app" / ".env")}
manifest = {
    "schemaVersion": 4,  # MANIFEST_SCHEMA_VERSION in desktop/src/main/docker-stack.ts — the app refuses any other
    "releaseId": f"lite-{version}",
    "releaseChannel": "stable",
    "releaseVariant": "lite",
    "authEnforced": False,
    "authProvider": "none",
    "credentialNames": ["OPENAI_API_KEY", "LLM_API_KEY", "ROBO_LLM_API_KEY", "ROBO_EMBED_API_KEY",
                        "ROBO_SEARCH_LLM_API_KEY"],
    "composeFile": "compose.yml",
    "imagePull": True,
    "images": images,
    "imageIds": ids,
    **({"imageDigests": digests} if len(digests) == len(IMAGES) + len(EXTERNAL_IMAGES) else {}),
    "imageSizes": sizes,
    "architect": {"python": args.python, "app": "architect/app", "entrypoint": "api.main:app"},
    "environment": environment,
    "source": {
        "workspace": "0" * 40,
        "ontological": head(lite_src / "ontological-db"),
        "architect": head(root),
        "openPencil": head(root / "open-pencil"),
        "analyzer": head(root / "robo-analyzer/robo-data-analyzer"),
        "catalog": head(root / "robo-analyzer/robo-data-catalog"),
        "fabric": head(root / "robo-analyzer/robo-data-fabric"),
        "frontend": head(root / "robo-analyzer/robo-data-frontend"),
        "parser": head(lite_src / "antlr-code-parser"),
        "gateway": head(lite_src / "api-gateway"),
    },
}
if digests_file and len(digests) != len(IMAGES) + len(EXTERNAL_IMAGES):
    raise SystemExit(f"[runtime] {digests_file} lists {len(digests) - len(EXTERNAL_IMAGES)} of {len(IMAGES)} images")
(out / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
total = sum(sizes.values())
print(f"[runtime] manifest: {len(images)} images, download {total / 1e9:.2f} GB"
      f"{' (pinned to pushed digests)' if digests else ' (no digests yet — pull by tag)'}")
for k in images:
    print(f"  {k:10} {images[k]}  {ids[k][:19]}  {sizes[k] / 1e6:6.0f} MB")
PY
}
