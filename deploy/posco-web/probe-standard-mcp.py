#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""POSCO 표준항목 MCP 현장 점검 — 표준 라이브러리만 쓴다(서버 python3 에 패키지가 없다).

    python3 probe-standard-mcp.py 주문번호
    python3 probe-standard-mcp.py 주문번호 EN
    python3 probe-standard-mcp.py 주문번호 http://ace.posco.com:8029/mcp
    python3 probe-standard-mcp.py 주문번호 raw          ← 받은 JSON 을 그대로도 찍는다
    python3 probe-standard-mcp.py 주문번호 proxy        ← http_proxy 환경변수를 따른다(기본은 무시)

따옴표 없이 친다. 인자 순서는 상관없다:
  http 로 시작   → MCP 주소 (없으면 ROBO_STANDARD_MCP_URL → 같은 폴더 .env → ace.posco.com)
  KO / EN        → languageCode
  raw · proxy    → 위 설명
  나머지         → 키워드(여러 낱말이면 빈칸으로 잇는다)

하는 일: 연결(initialize) → 도구 목록 → 한 건 조회 → 기대 칸 이름과 대조 → 상태 값 목록.
끝 줄의 `standardItemStatus 값` 을 받아 적어 온다 — `.env` 의 ROBO_STANDARD_ACTIVE_STATUSES 에 쓴다.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://ace.posco.com:8029/mcp"
TOOL = "searchDataDictionary"
TIMEOUT_S = 10
EXPECTED = [
    ("standardKoreanName", "표준항목명"),
    ("standardEnglishId", "표준항목ID"),
    ("stdItemValueType", "값유형구분"),
    ("dataLength", "데이터자리수"),
    ("decimalLength", "소수점자리수"),
    ("codeItem", "코드항목여부"),
    ("mesUnitOfMeasure", "MES_UOM"),
    ("macroMicroItemType", "macroMicroItemType"),
    ("supervisoryDept", "주관부서명"),
    ("standardItemStatus", "표준항목상태구분"),
    ("standardItemDefinitionContent", "정의"),
    ("standardItemManagementMethodExplanation", "운영방법"),
]


def say(msg=""):
    # LANG=C 터미널(python3.6)에서는 한글이 UnicodeEncodeError 로 죽는다 — 그때는 utf-8 로 바로 쓴다.
    try:
        sys.stdout.write(msg + "\n")
    except UnicodeEncodeError:
        sys.stdout.flush()
        sys.stdout.buffer.write((msg + "\n").encode("utf-8"))
    sys.stdout.flush()


def url_from_env_file():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ROBO_STANDARD_MCP_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def parse_args(argv):
    url, lang, raw, proxy, words = "", "KO", False, False, []
    for a in argv:
        low = a.lower()
        if low.startswith("http://") or low.startswith("https://"):
            url = a
        elif low in ("ko", "en"):
            lang = low.upper()
        elif low == "raw":
            raw = True
        elif low == "proxy":
            proxy = True
        else:
            words.append(a)
    url = url or os.environ.get("ROBO_STANDARD_MCP_URL", "").strip() or url_from_env_file() or DEFAULT_URL
    return url, lang, raw, proxy, " ".join(words).strip()


class Mcp(object):
    def __init__(self, url, use_proxy):
        self.url = url
        self.session_id = None
        self.protocol = None
        self.next_id = 1
        handlers = [] if use_proxy else [urllib.request.ProxyHandler({})]
        self.opener = urllib.request.build_opener(*handlers)

    def _post(self, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        if self.session_id:
            req.add_header("Mcp-Session-Id", self.session_id)
        if self.protocol:
            req.add_header("MCP-Protocol-Version", self.protocol)
        return self.opener.open(req, timeout=TIMEOUT_S)

    def request(self, method, params):
        rid = self.next_id
        self.next_id += 1
        resp = self._post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
        if sid:
            self.session_id = sid
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "text/event-stream" in ctype:
            return self._read_sse(resp, rid), "SSE"
        body = resp.read().decode("utf-8", "replace")
        return json.loads(body), "JSON"

    def _read_sse(self, resp, rid):
        # 이벤트는 빈 줄로 끝난다. data: 줄을 모아 id 가 맞는 응답이 나오면 멈춘다.
        buf = []
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith("data:"):
                buf.append(line[5:].lstrip())
                continue
            if line == "" and buf:
                text = "\n".join(buf)
                buf = []
                try:
                    msg = json.loads(text)
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get("id") == rid:
                    return msg
        if buf:
            msg = json.loads("\n".join(buf))
            if isinstance(msg, dict) and msg.get("id") == rid:
                return msg
        raise RuntimeError("SSE 가 끝났는데 id=%s 응답이 없다" % rid)

    def notify(self, method):
        try:
            self._post({"jsonrpc": "2.0", "method": method}).read()
        except urllib.error.HTTPError as e:
            if e.code not in (200, 202, 204):
                raise

    def close(self):
        if not self.session_id:
            return
        req = urllib.request.Request(self.url, method="DELETE")
        req.add_header("Mcp-Session-Id", self.session_id)
        try:
            self.opener.open(req, timeout=3).read()
        except Exception:
            pass


def find_entries(obj):
    if isinstance(obj, list):
        out = []
        for x in obj:
            out.extend(find_entries(x))
        return out
    if isinstance(obj, dict):
        if "standardKoreanName" in obj:
            return [obj]
        out = []
        for v in obj.values():
            if isinstance(v, (list, dict)):
                out.extend(find_entries(v))
        return out
    return []


def entries_from_result(result):
    sc = result.get("structuredContent")
    entries = find_entries(sc) if sc else []
    if not entries:
        for c in result.get("content") or []:
            text = c.get("text") if isinstance(c, dict) else None
            if not text:
                continue
            try:
                entries.extend(find_entries(json.loads(text)))
            except ValueError:
                say("   (JSON 이 아닌 글: %s)" % text[:200])
    return entries


def main():
    url, lang, raw, proxy, keyword = parse_args(sys.argv[1:])
    if not keyword:
        say(__doc__)
        return 2
    say("== POSCO 표준항목 MCP 점검")
    say("   주소     %s" % url)
    say("   키워드   %s   (languageCode=%s)" % (keyword, lang))
    say("   프록시   %s" % ("환경변수 따름" if proxy else "쓰지 않음"))
    mcp = Mcp(url, proxy)

    say("\n[1] 연결(initialize)")
    t0 = time.time()
    try:
        init, mode = mcp.request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "robo-probe", "version": "1"},
        })
    except urllib.error.HTTPError as e:
        say("   ✗ HTTP %s — %s" % (e.code, e.read()[:300].decode("utf-8", "replace")))
        return 1
    except Exception as e:
        say("   ✗ 닿지 않는다: %s: %s" % (type(e).__name__, e))
        say("     → 이 서버에서 주소·포트가 열렸는지 본다:  curl -sv %s" % url)
        return 1
    if "error" in init:
        say("   ✗ 서버 오류: %s" % json.dumps(init["error"], ensure_ascii=False))
        return 1
    info = init.get("result", {})
    mcp.protocol = info.get("protocolVersion")
    say("   ✓ %.0f ms · 응답 %s · 세션 %s" % ((time.time() - t0) * 1000, mode, mcp.session_id or "(없음 — stateless)"))
    say("   서버 %s · 프로토콜 %s" % (json.dumps(info.get("serverInfo"), ensure_ascii=False), info.get("protocolVersion")))
    mcp.notify("notifications/initialized")

    say("\n[2] 도구 목록")
    tools_msg, _ = mcp.request("tools/list", {})
    tools = (tools_msg.get("result") or {}).get("tools") or []
    for t in tools:
        say("   - %s" % t.get("name"))
    tool = [t for t in tools if t.get("name") == TOOL]
    if not tool:
        say("   ✗ %s 가 없다" % TOOL)
        mcp.close()
        return 1
    say("   ✓ %s 입력: %s" % (TOOL, json.dumps(tool[0].get("inputSchema", {}).get("properties", {}), ensure_ascii=False)))

    say("\n[3] 조회")
    t0 = time.time()
    call, mode = mcp.request("tools/call", {"name": TOOL, "arguments": {"keyword": keyword, "languageCode": lang}})
    ms = (time.time() - t0) * 1000
    mcp.close()
    if "error" in call:
        say("   ✗ 서버 오류: %s" % json.dumps(call["error"], ensure_ascii=False))
        return 1
    result = call.get("result") or {}
    if raw:
        say(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("isError"):
        say("   ✗ 도구 오류: %s" % json.dumps(result.get("content"), ensure_ascii=False)[:500])
        return 1
    entries = entries_from_result(result)
    say("   ✓ %.0f ms · %d 건 · 모양 %s" % (ms, len(entries), "structuredContent" if result.get("structuredContent") else "content[].text"))

    say("\n[4] 칸 이름 대조")
    seen = set()
    for e in entries:
        seen.update(e.keys())
    names = [k for k, _ in EXPECTED]
    for k, label in EXPECTED:
        filled = sum(1 for e in entries if e.get(k) not in (None, ""))
        mark = "✓" if k in seen else "✗ 없음"
        say("   %-42s %-14s %s  (값 있음 %d/%d)" % (k, label, mark, filled, len(entries)))
    extra = sorted(seen - set(names))
    if extra:
        say("   기대에 없던 칸: %s" % ", ".join(extra))

    say("\n[5] 결과 (최대 5건)")
    exact = 0
    for e in entries[:5]:
        say("   · %s  %s  유형=%s 자리=%s 소수=%s 코드=%s 상태=%s" % (
            e.get("standardKoreanName"), e.get("standardEnglishId"), e.get("stdItemValueType"),
            e.get("dataLength"), e.get("decimalLength"), e.get("codeItem"), e.get("standardItemStatus")))
    for e in entries:
        if "".join(str(e.get("standardKoreanName") or "").split()) == "".join(keyword.split()):
            exact += 1
    say("   이름이 정확히 같은 것: %d 건  (1 건이어야 설계에 붙는다)" % exact)

    statuses = sorted(set(str(e.get("standardItemStatus")) for e in entries))
    say("\n   standardItemStatus 값: %s" % (", ".join(statuses) if statuses else "(결과 없음)"))
    say("   → '사용 중' 인 값을 .env 의 ROBO_STANDARD_ACTIVE_STATUSES 에 쉼표로 적는다")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
