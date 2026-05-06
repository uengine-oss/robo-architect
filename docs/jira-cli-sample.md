
#!/usr/bin/env python3
"""Confluence 페이지 조회 CLI 애플리케이션"""

import requests
import json
import sys
from html.parser import HTMLParser

# Confluence 설정
BASE_URL = "https://uengine-team.atlassian.net/wiki/api/v2"
AUTH = ("jyjang@uengine.org", "ATATT3xFfGF0Hi4VrieqMrXJI-R3y6GEWb0K2Xuyw6wIVSGrwbCUq9fm0sT4K-tOSyRdNSFOVe4xHwIdtiFNYeGACB1e1TJz95ppodW7qcBp7gUSRPY0HV6LUS2E3DfzuKclXbSVSpyfYeaBEZyUj2JOtDQ1U6trsd3gwXudepmgXGdsLFGbTUY=25A30F2C")
HEADERS = {"Accept": "application/json"}


class HTMLTextExtractor(HTMLParser):
    """HTML에서 텍스트만 추출하는 파서"""

    def __init__(self):
        super().__init__()
        self.result = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.result.append("\n")
        if tag == "li":
            self.result.append("  • ")

    def handle_data(self, data):
        self.result.append(data)

    def get_text(self):
        return "".join(self.result).strip()


def html_to_text(html):
    """HTML을 읽기 좋은 텍스트로 변환"""
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def get_pages():
    """Confluence 페이지 목록 조회"""
    pages = []
    url = f"{BASE_URL}/pages"
    params = {"limit": 50, "sort": "-modified-date"}

    while url:
        resp = requests.get(url, auth=AUTH, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        pages.extend(data.get("results", []))

        # 다음 페이지가 있으면 계속 조회
        next_link = data.get("_links", {}).get("next")
        if next_link:
            url = f"https://uengine-team.atlassian.net/wiki{next_link}"
            params = None  # next URL에 파라미터가 이미 포함됨
        else:
            url = None

    return pages


def get_page_content(page_id):
    """특정 페이지의 내용 조회"""
    url = f"{BASE_URL}/pages/{page_id}"
    params = {"body-format": "storage"}
    resp = requests.get(url, auth=AUTH, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()


def display_pages(pages):
    """페이지 목록 출력"""
    print("\n" + "=" * 60)
    print("  Confluence 페이지 목록")
    print("=" * 60)
    for i, page in enumerate(pages, 1):
        title = page.get("title", "(제목 없음)")
        page_id = page.get("id", "")
        print(f"  [{i:3d}] {title}  (ID: {page_id})")
    print("=" * 60)


def display_page_content(page_data):
    """페이지 내용 출력"""
    title = page_data.get("title", "(제목 없음)")
    body_html = page_data.get("body", {}).get("storage", {}).get("value", "")

    print("\n" + "=" * 60)
    print(f"  📄 {title}")
    print("=" * 60)

    if body_html:
        text = html_to_text(body_html)
        print(text)
    else:
        print("  (내용이 비어있습니다)")

    print("\n" + "=" * 60)


def main():
    print("\n🔗 Confluence 페이지 조회 CLI")
    print("페이지 목록을 불러오는 중...")

    try:
        pages = get_pages()
    except requests.RequestException as e:
        print(f"오류: 페이지 목록을 가져올 수 없습니다 - {e}")
        sys.exit(1)

    if not pages:
        print("조회된 페이지가 없습니다.")
        sys.exit(0)

    display_pages(pages)

    while True:
        try:
            user_input = input("\n페이지 번호를 입력하세요 (q: 종료): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if user_input.lower() == "q":
            print("종료합니다.")
            break

        try:
            idx = int(user_input)
            if idx < 1 or idx > len(pages):
                print(f"1~{len(pages)} 사이의 번호를 입력하세요.")
                continue
        except ValueError:
            print("숫자 또는 'q'를 입력하세요.")
            continue

        selected = pages[idx - 1]
        page_id = selected["id"]

        print(f"\n'{selected['title']}' 페이지를 불러오는 중...")
        try:
            page_data = get_page_content(page_id)
            display_page_content(page_data)
        except requests.RequestException as e:
            print(f"오류: 페이지 내용을 가져올 수 없습니다 - {e}")


if __name__ == "__main__":
    main()
