# AESF - AI Event Storming Facilitator

WebRTC 기반 실시간 화상회의 + AI 퍼실리테이션 이벤트 스토밍 플랫폼

## 🎬 데모 영상

[![Event Storming Demo](https://img.youtube.com/vi/9e-vO8iKR-U/0.jpg)](https://youtu.be/9e-vO8iKR-U)
[![AI Facilitator Demo](https://img.youtube.com/vi/qi7mGj3whCI/0.jpg)](https://youtu.be/qi7mGj3whCI)
[![WebRTC Video Demo](https://img.youtube.com/vi/r7U4eBbcLvY/0.jpg)](https://youtu.be/r7U4eBbcLvY)

## 🎯 주요 기능

- **실시간 화상회의**: WebRTC 기반 P2P 비디오/오디오 통화
- **협업 캔버스**: 실시간 동시 편집 가능한 이벤트 스토밍 보드
- **AI 퍼실리테이터**: OpenAI Realtime API를 활용한 실시간 음성 가이드
- **규칙 검증**: 이벤트 스토밍 규칙 실시간 체크 (과거형, 이벤트 vs 커맨드 등)
- **그래프 저장**: Neo4j 기반 관계형 데이터 구조

## 🏗️ 기술 스택

### Frontend
- Vue 3 + TypeScript
- Pinia (상태 관리)
- Socket.IO Client (실시간 동기화)
- WebRTC (화상회의)

### Backend
- FastAPI (Python)
- python-socketio (WebSocket)
- OpenAI API (GPT-4, Whisper, Realtime)
- LangChain (AI 오케스트레이션)

### Database
- Neo4j (그래프 데이터베이스)
- Redis (세션 캐시)

### Infrastructure
- Docker Compose
- coturn (TURN/STUN 서버)

## 🚀 시작하기

### 1. 환경 설정

```bash
# .env 파일 확인 (이미 생성됨)
cat .env
```

`.env`가 없거나 새로 구성해야 한다면 `env.example`를 참고해서 생성하세요.

추가로 Neo4j 멀티-데이터베이스를 사용하는 경우, 아래 설정을 `.env`에 지정할 수 있습니다.

- **`NEO4J_DATABASE`**: 사용할 Neo4j database 이름 (기본값: `neo4j`)

### 2. Docker 서비스 시작

```bash
docker-compose up -d
```

### 3. Backend 실행

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:socket_app --reload --host 0.0.0.0 --port 8000
```

### 4. Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

### 5. 접속

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Neo4j Browser: http://localhost:7474

## 📁 프로젝트 구조

> 기능(비즈니스 capability) 기준으로 먼저 묶고, 각 기능 내부에서 API/UI/상태 등을 구성합니다.

```
robo-agile-facilitator/
├── api/
│   │   ├── config.py
│   │   ├── main.py
│   │   └── features/
│   │       ├── ai_facilitator/        # OpenAI Realtime 기반 AI 퍼실리테이션
│   │       │   ├── facilitator.py
│   │       │   └── realtime_api.py
│   │       ├── event_storming/        # 세션/캔버스 도메인(스티커/연결/내보내기)
│   │       │   ├── http_api.py
│   │       │   ├── export_api.py
│   │       │   ├── graph_store.py
│   │       │   └── models.py
│   │       └── workshop_realtime/     # 실시간 워크샵(소켓/프레즌스/비디오 시그널링)
│   │           ├── server.py
│   │           ├── canvas_handlers.py
│   │           ├── presence_store.py
│   │           └── video_signaling.py
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   ├── router/
│   │   ├── style.css
│   │   └── features/
│   │       ├── eventStorming/         # 이벤트 스토밍 워크샵 UX (페이지/캔버스/세션 UI/상태)
│   │       │   ├── pages/
│   │       │   ├── state/
│   │       │   └── ui/
│   │       ├── workshopRealtime/      # WebRTC 화상회의(패널/상태)
│   │       │   ├── state/
│   │       │   └── ui/
│   │       └── aiFacilitator/         # AI 퍼실리테이터 UI
│   │           └── ui/
│   └── package.json
└── requirements.txt
├── docker-compose.yml
├── turnserver.conf
└── .env
```

## 🔧 API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/sessions` | 새 세션 생성 |
| GET | `/api/sessions/{id}` | 세션 정보 조회 |
| POST | `/api/realtime/ephemeral-key` | OpenAI Realtime 키 발급 |
| WS | `/socket.io` | 캔버스 동기화 + 시그널링 |

## 🎨 스티커 타입

| 타입 | 색상 | 설명 |
|------|------|------|
| Event | 🟠 Orange | 도메인 이벤트 (과거형) |
| Command | 🔵 Blue | 명령 (이벤트 트리거) |
| Policy | 🟣 Purple | 정책 (When X, do Y) |
| Read Model | 🟢 Green | 읽기 모델 |
| External System | 🔴 Pink | 외부 시스템 |

## 📋 세션 흐름

1. **오리엔테이션** (5분) - 도메인 소개
2. **이벤트 도출** (10분) - 브레인스토밍
3. **이벤트 정제** (15분) - 규칙 검증
4. **커맨드/정책** (15분) - 트리거 추가
5. **타임라인 정렬** (10분) - 시간순 배치
6. **요약** (5분) - 결과 정리

## 🤖 AI 기능

### 실시간 음성 대화
OpenAI Realtime API를 통해 음성으로 AI와 대화

### 규칙 검증
- 이벤트가 과거형인지 확인
- 커맨드와 이벤트 구분
- 세션 단계별 가이드

### 교육 지원
- 이벤트 스토밍 개념 설명
- 실시간 피드백 제공

## 📝 License

MIT


