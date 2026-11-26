#!/usr/bin/env bash
# =====================================================================
# 컨테이너 저장소(podman — 이미지 · 컨테이너 · 볼륨 전부)를 큰 파티션으로 옮긴다.
#
#   sudo bash move-storage.sh check    /MSAEZ/containers/storage   # 미리 보기 — 아무것도 안 바꾼다
#   sudo bash move-storage.sh move     /MSAEZ/containers/storage   # 옮긴다(컨테이너가 잠깐 멈춘다)
#   sudo bash move-storage.sh verify                               # 옮기기 전 기록과 대조
#   sudo bash move-storage.sh rollback                             # 옛 자리로 되돌린다
#   sudo bash move-storage.sh abort                                # move 가 바꿔 끼우기 전에 멈췄을 때 — 그대로 다시 띄운다
#   sudo bash move-storage.sh cleanup                              # 며칠 뒤 — 옛 사본을 지워 루트 공간을 돌려받는다
#
# ## 어떻게 옮기나 — 경로는 그대로, 아래 디스크만 바꾼다(bind mount)
#
# `storage.conf` 의 graphroot 를 바꾸는 방법은 쓰지 않는다. podman 은 자기 DB(libpod)에
# 저장소 경로와 **볼륨마다의 경로**를 적어 두어, 경로가 바뀌면
# "database graph root … does not match" 로 멈추거나 볼륨이 옛 경로를 가리킨다.
# 그래서 내용을 큰 파티션에 통째 복사하고, 그 폴더를 원래 경로(/var/lib/containers/storage)
# 에 bind mount 한다. podman 이 보는 경로 · 설정 · DB 는 한 글자도 안 바뀐다.
#
#   1 기록      이미지 · 볼륨 · 컨테이너 목록과 볼륨별 크기 → <대상 옆>/move-record-<시각>/
#   2 멈춤      떠 있던 컨테이너를 기록(시작 순서)하고 멈춤 → podman 소켓 · 서비스 멈춤
#   3 복사      rsync -aHAX --numeric-ids (SELinux 라벨 · 하드링크 · overlay xattr 그대로)
#               → 한 번 더 돌려 차이 0 인지 확인
#   4 바꿔 끼움  옛 폴더 이름을 storage.before-move-<시각> 으로 바꾸고(같은 디스크라 즉시)
#               빈 폴더에 bind mount · /etc/fstab 에 한 줄(백업을 남김)
#   5 대조      podman 이 보는 이미지 · 볼륨 · 컨테이너 · 볼륨 크기가 기록과 같은지
#   6 다시 띄움  서비스 → 멈췄던 컨테이너를 **멈춘 그 컨테이너 그대로** 원래 시작 순서로 start
#               (compose up 이 아니다 — 아무것도 다시 만들지 않는다)
#
# 옛 사본은 cleanup 전까지 루트에 남는다(되돌리기용). 루트 공간은 cleanup 뒤에 돌아온다.
# 이 스크립트는 이미지 · 볼륨을 **지우지 않는다**(prune 없음). cleanup 만 옛 사본 폴더를 지운다.
# =====================================================================
set -euo pipefail

SRC=/var/lib/containers/storage
STATE=/var/lib/containers/.move-storage.state
FSTAB=/etc/fstab
TAG="# robo move-storage.sh"

say()  { printf '%s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
die()  {
  printf '\n✖ %s\n' "$*" >&2
  if [ "${cmd:-}" = move ] && [ -f "$STATE" ]; then  # move 가 중간에 멈췄다 — 다음에 칠 것
    case "$(sed -n 's/^PHASE=//p' "$STATE")" in
      recorded|copied) printf '  → 옛 자리는 그대로다. 컨테이너를 다시 띄우려면: sudo bash %s abort\n' "$0" >&2 ;;
      *)               printf '  → 바꿔 끼운 뒤다: sudo bash %s rollback\n' "$0" >&2 ;;
    esac
  fi
  exit 1
}
ok()   { printf '  ✔ %s\n' "$*"; }
warn() { printf '  ⚠ %s\n' "$*"; }

[ "$(id -u)" = 0 ] || die "root 로 — sudo bash $0 $*"
command -v podman >/dev/null || die "podman 이 없다"

pinfo() { podman info --format "$1" 2>/dev/null || true; }

record() {  # $1 = 폴더 — podman 이 지금 보는 것을 적는다
  local d=$1; mkdir -p "$d"
  podman images -a --format '{{.ID}} {{.Repository}}:{{.Tag}}' | sort > "$d/images.txt"
  podman volume ls --format '{{.Name}}' | sort > "$d/volumes.txt"
  podman ps -a --format '{{.ID}} {{.Names}} {{.Image}}' | sort > "$d/containers.txt"
  : > "$d/volume-sizes.txt"
  while read -r v; do
    [ -n "$v" ] || continue
    mp=$(podman volume inspect --format '{{.Mountpoint}}' "$v")
    printf '%s %s %s\n' "$v" "$(du -sb "$mp" 2>/dev/null | cut -f1)" "$mp" >> "$d/volume-sizes.txt"
  done < "$d/volumes.txt"
}

compare() {  # $1 기록 · $2 지금 — 같으면 0
  local a=$1 b=$2 bad=0 f
  for f in images.txt volumes.txt containers.txt volume-sizes.txt; do
    if diff -q "$a/$f" "$b/$f" >/dev/null; then ok "$f 같음 ($(wc -l < "$a/$f") 줄)"
    else warn "$f 다름:"; diff "$a/$f" "$b/$f" | head -20; bad=1; fi
  done
  return $bad
}

stop_podman() {
  systemctl stop podman.socket podman.service 2>/dev/null || true
  local n
  n=$(podman ps -q | wc -l)
  [ "$n" = 0 ] || die "아직 떠 있는 컨테이너 $n 개 — podman ps"
  # conmon 은 stop 뒤 정리를 마치고 곧(1초 안팎) 끝난다 — 기다린다. 좀비(Z)는 이미 끝난 것.
  local w
  for w in $(seq 1 30); do
    ps -eo stat=,comm= | awk '$2 == "conmon" && $1 !~ /^Z/ {found=1} END {exit !found}' || break
    sleep 1
  done
  if ps -eo stat=,comm= | awk '$2 == "conmon" && $1 !~ /^Z/ {found=1} END {exit !found}'; then
    die "30초 기다려도 conmon 이 남아 있다 — ps -ef | grep conmon"
  fi
  # 저장소 안의 마운트: 컨테이너 merged(멈추면 곧 풀린다) · overlay 폴더의 자기 bind(containers/storage 가 건다)
  local i inner
  for i in $(seq 1 30); do
    inner=$(findmnt -rn -o TARGET | grep "^$SRC/" | grep -vx "$SRC/overlay" || true)
    [ -z "$inner" ] && break
    sleep 1
  done
  [ -z "$inner" ] || die "저장소 안에 마운트가 남아 있다(podman mount?):
$inner"
  if findmnt -n "$SRC/overlay" >/dev/null 2>&1; then umount "$SRC/overlay"; fi
}

start_recorded() {  # $1 = running.txt (시작 순서)
  systemctl start podman.socket 2>/dev/null || true
  local name
  while read -r _ name; do
    [ -n "$name" ] || continue
    podman start "$name" >/dev/null && ok "start $name" || warn "start 실패: $name"
  done < "$1"
}

load_state() { [ -f "$STATE" ] || die "옮긴 기록이 없다($STATE)"; . "$STATE"; }

fstype_check() {  # $1 = 대상 폴더(있는 부모 기준)
  local p=$1 mnt fs
  while [ ! -e "$p" ]; do p=$(dirname "$p"); done
  mnt=$(findmnt -n -o TARGET --target "$p"); fs=$(findmnt -n -o FSTYPE --target "$p")
  say "  대상 파티션: $mnt ($fs)"
  if [ "$fs" = xfs ]; then
    if xfs_info "$mnt" 2>/dev/null | grep -q 'ftype=1'; then ok "xfs ftype=1 (overlay 가능)"
    else die "xfs ftype=1 이 아니다 — overlay 저장소를 둘 수 없다(서버 담당자와)"; fi
  fi
  case "$fs" in xfs|ext4) ;; *) warn "파일시스템 $fs — 확인 필요(xfs/ext4 권장)";; esac
  [ "$mnt" != / ] || die "대상이 루트 파티션 안이다 — 옮기는 의미가 없다"
  MNT=$mnt
}

cmd=${1:-check}
DST=${2:-}

case "$cmd" in
# ---------------------------------------------------------------------
check)
  [ -n "$DST" ] || die "대상 폴더 — sudo bash $0 check /MSAEZ/containers/storage"
  step "podman"
  say "  $(podman --version) · driver $(pinfo '{{.Store.GraphDriverName}}') · db $(pinfo '{{.Host.DatabaseBackend}}')"
  GR=$(pinfo '{{.Store.GraphRoot}}'); VP=$(pinfo '{{.Store.VolumePath}}')
  say "  graphroot $GR · volume path ${VP:-?}"
  [ "$GR" = "$SRC" ] || die "graphroot 가 $SRC 가 아니다 — 이 스크립트의 전제와 다르다(멈춤)"
  [ -z "$VP" ] || [[ "$VP" == "$SRC"* ]] || warn "볼륨 경로가 저장소 밖이다($VP) — 볼륨은 안 옮겨진다"
  if findmnt -n "$SRC" >/dev/null; then warn "$SRC 는 이미 마운트다: $(findmnt -n -o SOURCE "$SRC") — 옮긴 적이 있나?"; fi
  [ -f "$STATE" ] && warn "옮긴 기록이 있다($STATE)"
  step "크기"
  USED=$(du -sxb "$SRC" | cut -f1)
  say "  지금 저장소 $(numfmt --to=iec "$USED") (루트: $(df -h --output=used,avail,pcent / | tail -1))"
  fstype_check "$DST"
  FREE=$(df -B1 --output=avail "$MNT" | tail -1)
  say "  대상 여유 $(numfmt --to=iec "$FREE")"
  [ "$FREE" -gt $((USED * 12 / 10)) ] && ok "여유가 저장소의 1.2배를 넘는다" || die "대상 여유가 모자란다"
  if [ -e "$DST" ] && [ -n "$(ls -A "$DST" 2>/dev/null)" ]; then die "대상 폴더가 비어 있지 않다: $DST"; fi
  ok "대상 폴더가 없거나 비어 있다"
  step "멈출 컨테이너(떠 있는 것 — 다른 앱 포함)"
  if [ -n "$(podman ps -q)" ]; then
    podman ps --format '  {{.Names}}  ({{.Image}})  {{.Status}}'
    say "  compose 프로젝트: $(podman ps --format '{{index .Labels "com.docker.compose.project"}}' | sort -u | tr '\n' ' ')"
  else say "  (없음)"; fi
  say "  전체: 이미지 $(podman images -a -q | wc -l) · 볼륨 $(podman volume ls -q | wc -l) · 컨테이너 $(podman ps -a -q | wc -l)"
  step "도구"
  for t in rsync findmnt numfmt; do command -v $t >/dev/null && ok "$t" || die "$t 이 없다"; done
  SEL=$(getenforce 2>/dev/null || echo 없음); say "  SELinux: $SEL"
  if [ "$SEL" != 없음 ] && [ "$SEL" != Disabled ]; then
    command -v semanage >/dev/null && ok "semanage" || warn "semanage 없음 — 라벨은 rsync 가 그대로 옮기지만, 나중 restorecon 대비 규칙은 못 넣는다"
    say "  지금 라벨: $(ls -Zd "$SRC" | awk '{print $1}')"
  fi
  systemctl is-active podman.socket >/dev/null 2>&1 && say "  podman.socket 켜짐(옮길 때 멈췄다 다시 켠다)" || true
  step "예상"
  say "  복사 $(numfmt --to=iec "$USED") — 디스크 속도에 따라 수 분~수십 분, 그동안 컨테이너가 멈춘다"
  say "  → 문제 없으면: sudo bash $0 move $DST"
  ;;
# ---------------------------------------------------------------------
move)
  [ -n "$DST" ] || die "대상 폴더 — sudo bash $0 move /MSAEZ/containers/storage"
  [ ! -f "$STATE" ] || die "이미 옮긴 기록이 있다($STATE) — verify / rollback / cleanup"
  findmnt -n "$SRC" >/dev/null && die "$SRC 가 이미 마운트다"
  [ -f "$FSTAB" ] || die "$FSTAB 이 없다"
  ! grep -qF "$TAG" "$FSTAB" || die "fstab 에 이 스크립트 줄이 이미 있다 — 재부팅 때 두 번 걸린다: grep robo $FSTAB"
  [ "$(pinfo '{{.Store.GraphRoot}}')" = "$SRC" ] || die "graphroot 가 $SRC 가 아니다"
  fstype_check "$DST"
  if [ -e "$DST" ] && [ -n "$(ls -A "$DST" 2>/dev/null)" ]; then die "대상 폴더가 비어 있지 않다: $DST"; fi
  TS=$(date +%Y%m%d-%H%M%S)
  REC="$(dirname "$DST")/move-record-$TS"; OLD="$SRC.before-move-$TS"

  step "1 기록 → $REC"
  mkdir -p "$REC"
  for c in $(podman ps -q); do podman inspect --format '{{.State.StartedAt.UnixNano}} {{.Name}}' "$c"; done \
    | sort -n > "$REC/running.txt"   # 시작한 순서 — 다시 띄울 때 그 순서로
  cp -a "$FSTAB" "$REC/fstab.before"
  ok "떠 있던 것 $(wc -l < "$REC/running.txt") · fstab 백업"
  cat > "$STATE" <<EOF
DST='$DST'
OLD='$OLD'
REC='$REC'
MNT='$MNT'
PHASE=recorded
EOF

  trap 'printf "
  → move 가 중간에 멈췄다. 상태: $(grep PHASE "$STATE" 2>/dev/null) — 바꿔 끼우기 전이면 sudo bash $0 abort, 뒤면 rollback
" >&2' ERR
  step "2 멈춤"
  tac "$REC/running.txt" | while read -r _ name; do podman stop -t 60 "$name" >/dev/null && ok "stop $name"; done
  stop_podman; ok "podman 멈춤"
  record "$REC/before"   # 멈춘 뒤에 — 떠 있는 동안 재면 볼륨 크기가 그새 바뀐다
  ok "기록: 이미지 $(wc -l < "$REC/before/images.txt") · 볼륨 $(wc -l < "$REC/before/volumes.txt") · 컨테이너 $(wc -l < "$REC/before/containers.txt")"

  step "3 복사 $SRC → $DST"
  mkdir -p "$DST"
  rsync -aHAX --numeric-ids --info=progress2 "$SRC/" "$DST/"
  left=$(rsync -aHAXn --numeric-ids --delete --itemize-changes "$SRC/" "$DST/" | wc -l)
  [ "$left" = 0 ] || die "두 번째 rsync 에 차이 $left 줄 — 옛 자리는 그대로다(컨테이너는 멈춘 채). 다시 move 전에 $STATE · $DST 확인"
  ok "차이 0"
  sed -i 's/^PHASE=.*/PHASE=copied/' "$STATE"
  if [ "$(getenforce 2>/dev/null || echo Disabled)" != Disabled ]; then  # SELinux 라벨이 그대로 왔나 — 다르면 컨테이너가 볼륨을 못 읽는다
    bad=0
    for rel in . overlay volumes libpod $(cd "$SRC" && ls -d volumes/*/_data 2>/dev/null | head -5); do
      [ -e "$SRC/$rel" ] || continue
      a=$(stat -c %C "$SRC/$rel"); b=$(stat -c %C "$DST/$rel")
      [ "$a" = "$b" ] || { warn "라벨 다름 $rel: $a → $b"; bad=1; }
    done
    [ "$bad" = 0 ] || die "SELinux 라벨이 다르게 복사됐다 — 옛 자리는 그대로다: sudo bash $0 abort"
    ok "SELinux 라벨 같음"
  fi

  step "4 바꿔 끼움"
  sed -i 's/^PHASE=.*/PHASE=swapping/' "$STATE"   # 여기부터는 abort 가 아니라 rollback
  mv "$SRC" "$OLD"; mkdir "$SRC"
  chcon --reference="$OLD" "$SRC" 2>/dev/null || true
  chmod --reference="$OLD" "$SRC"
  mount --bind "$DST" "$SRC"
  printf '%s %s none bind,x-systemd.requires-mounts-for=%s 0 0 %s\n' "$DST" "$SRC" "$MNT" "$TAG" >> "$FSTAB"
  systemctl daemon-reload 2>/dev/null || true
  if command -v semanage >/dev/null && [ "$(getenforce 2>/dev/null || echo Disabled)" != Disabled ]; then
    semanage fcontext -a -e /var/lib/containers "$(dirname "$DST")" 2>/dev/null && ok "SELinux 같은 라벨 규칙: $(dirname "$DST") = /var/lib/containers" || warn "semanage 규칙 추가 실패(이미 있을 수 있음)"
  fi
  sed -i 's/^PHASE=.*/PHASE=mounted/' "$STATE"
  ok "$SRC ← $DST (fstab 백업 $REC/fstab.before)"

  step "5 대조(띄우기 전)"
  record "$REC/after"
  compare "$REC/before" "$REC/after" || die "기록과 다르다 — 컨테이너를 안 띄웠다. 되돌리기: sudo bash $0 rollback"

  step "6 다시 띄움(멈춘 그 컨테이너를, 원래 시작 순서로)"
  start_recorded "$REC/running.txt"
  sed -i 's/^PHASE=.*/PHASE=done/' "$STATE"
  trap - ERR
  step "끝"
  say "  루트: $(df -h --output=used,avail,pcent / | tail -1)  (옛 사본 $OLD 이 남아 있어 아직 안 줄었다)"
  say "  확인: sudo docker compose ps -a (앱 폴더마다) · 화면 · sudo bash $0 verify"
  say "  며칠 뒤 문제 없으면: sudo bash $0 cleanup  /  문제 있으면: sudo bash $0 rollback"
  ;;
# ---------------------------------------------------------------------
verify)
  load_state
  step "마운트"
  findmnt "$SRC" || die "$SRC 가 마운트가 아니다"
  grep -qF "$TAG" "$FSTAB" && ok "fstab 줄 있음(재부팅해도 유지)" || warn "fstab 줄이 없다"
  step "기록과 대조(볼륨 크기는 앱이 쓰면 달라진다 — 참고용)"
  record "$REC/verify"
  compare "$REC/before" "$REC/verify" || true
  step "떠 있던 것"
  while read -r _ name; do
    st=$(podman inspect --format '{{.State.Status}}' "$name" 2>/dev/null || echo 없음)
    [ "$st" = running ] && ok "$name running" || warn "$name $st"
  done < "$REC/running.txt"
  ;;
# ---------------------------------------------------------------------
rollback)
  load_state
  [ -d "$OLD" ] || die "옛 사본($OLD)이 없다 — cleanup 뒤에는 되돌릴 수 없다"
  step "멈춤"
  for c in $(podman ps -q); do podman stop -t 60 "$c" >/dev/null; done
  stop_podman
  step "옛 자리로"
  if findmnt -n "$SRC" >/dev/null; then umount "$SRC"; fi
  if [ -d "$SRC" ]; then rmdir "$SRC" || die "$SRC 가 비어 있지 않다 — 손으로 확인"; fi
  mv "$OLD" "$SRC"
  { grep -vF "$TAG" "$FSTAB" || true; } > "$FSTAB.tmp"   # 이 줄만 있으면 grep 이 1 로 끝난다 — 그래도 써야 한다
  cat "$FSTAB.tmp" > "$FSTAB"; rm -f "$FSTAB.tmp"
  ! grep -qF "$TAG" "$FSTAB" || die "fstab 에서 줄을 못 뺐다 — 손으로: $FSTAB"
  systemctl daemon-reload 2>/dev/null || true
  ok "$SRC = 옛 폴더 · fstab 줄 뺌"
  step "다시 띄움"
  start_recorded "$REC/running.txt"
  mv "$STATE" "$REC/state.rolled-back"
  say "  큰 파티션의 사본 $DST 는 남겨 두었다(옮긴 뒤 쓴 내용은 거기에만 있다). 필요 없으면 직접 지운다."
  ;;
# ---------------------------------------------------------------------
abort)
  load_state
  case "${PHASE:-}" in recorded|copied) ;; *) die "PHASE=${PHASE:-?} — 바꿔 끼운 뒤다. rollback 을 쓴다";; esac
  findmnt -n "$SRC" >/dev/null && die "$SRC 가 마운트다 — rollback 을 쓴다"
  [ -d "$SRC/libpod" ] || [ -d "$SRC/overlay" ] || die "$SRC 에 저장소가 안 보인다 — 손대지 않는다"
  step "옛 자리 그대로 다시 띄움"
  start_recorded "$REC/running.txt"
  step "만들다 만 사본 지움: $DST"
  rm -rf --one-file-system "$DST"
  mv "$STATE" "$REC/state.aborted"
  ok "처음 상태 — 다시 하려면 check 부터"
  ;;
# ---------------------------------------------------------------------
cleanup)
  load_state
  [ "${PHASE:-}" = done ] || die "옮기기가 끝나지 않았다(PHASE=${PHASE:-?})"
  findmnt -n "$SRC" >/dev/null || die "$SRC 가 마운트가 아니다 — 지우지 않는다"
  [ -d "$OLD" ] || die "옛 사본이 없다($OLD)"
  say "  지울 것: $OLD ($(du -sxh "$OLD" | cut -f1)) — 되돌리기는 더 못 한다"
  read -r -p "  지우려면 YES: " a
  [ "$a" = YES ] || die "그만둠"
  rm -rf --one-file-system "$OLD"
  mv "$STATE" "$REC/state.done"
  ok "지움 — 루트: $(df -h --output=used,avail,pcent / | tail -1)"
  ;;
*) die "check | move | verify | rollback | abort | cleanup" ;;
esac
