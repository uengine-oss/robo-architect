#!/usr/bin/env bash
# Can an anonymous client pull every release image? (The app pulls without logging in.)
#
#   scripts/release/check-images-public.sh [--version 0.1.0] [--variant age-fabric]
#   (age-fabric: also the edition's own package robo-architect-lite-fabric-db)
#
# Exit 0 when every manifest answers 200 without credentials; otherwise lists the
# package settings pages where the visibility has to be switched to Public, and exits 3.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
VERSION=$(node -p "require('$ROOT/desktop/package.json').version")
COMPONENTS="graph-db graph-bolt analyzer catalog fabric parser gateway wireframe"
while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION=$2; shift 2 ;;
    --variant) case "$2" in age-fabric) COMPONENTS="$COMPONENTS fabric-db" ;; ontological) ;; *) echo "--variant is age-fabric" >&2; exit 2 ;; esac; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
ORG=uengine-oss
ACCEPT='application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'
private=""
for component in $COMPONENTS; do
  pkg="robo-architect-lite-$component"
  token=$(curl -fsS "https://ghcr.io/token?scope=repository:$ORG/$pkg:pull" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))' 2>/dev/null || true)
  code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $token" -H "Accept: $ACCEPT" \
    "https://ghcr.io/v2/$ORG/$pkg/manifests/$VERSION")
  if [ "$code" = 200 ]; then
    printf '  public   %s:%s\n' "$pkg" "$VERSION"
  else
    printf '  %-8s %s:%s\n' "($code)" "$pkg" "$VERSION"
    private="$private $pkg"
  fi
done
if [ -n "$private" ]; then
  echo
  echo "Not pullable anonymously yet. For each package: open the page, Danger Zone › Change visibility ›"
  echo "Public › type the package name › I understand, change package visibility."
  for pkg in $private; do echo "  https://github.com/orgs/$ORG/packages/container/$pkg/settings"; done
  exit 3
fi
echo "all stack images can be pulled anonymously"
