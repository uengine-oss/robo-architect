# tiktoken-cache

tiktoken 이 처음 쓸 때 인터넷(`openaipublic.blob.core.windows.net`)에서 받는 사전 두 개.
사내망 서버는 거기에 못 닿아 `HTTPSConnectionPool … 443` 으로 실패했다(2026-11-13 현장).
compose 가 이 폴더를 architect-api · catalog · analyzer 에 `/opt/tiktoken-cache` 로 붙이고
`TIKTOKEN_CACHE_DIR` 로 가리킨다.

| 파일(= 원본 URL 의 sha1) | 사전 | 쓰는 곳 |
|---|---|---|
| `9b5ad71b2ce5302211f9c61530b329a4922fc6a4` | cl100k_base | text-embedding-3-small · 토큰 세기 |
| `fb374d419588a4632f3f557e76b4b70aebbca790` | o200k_base | gpt-4.1 |

⚠ 파일을 고치지 않는다 — tiktoken 이 sha256 으로 대조한다(`.gitattributes` 가 줄바꿈 변환을 막는다).
다시 만들기: `TIKTOKEN_CACHE_DIR=<이 폴더> python -c "import tiktoken; [tiktoken.get_encoding(n) for n in ('cl100k_base','o200k_base')]"`
