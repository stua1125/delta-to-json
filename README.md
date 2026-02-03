# SSE Delta Log Aggregator

SSE(Server-Sent Events) 스트리밍 로그를 파싱하여 완전한 텍스트와 JSON으로 변환하는 웹 서비스입니다.

## 🚀 주요 기능

### 지원 포맷
| 포맷 | 설명 | 데이터 경로 |
|-----|------|------------|
| **Auto** | 자동 포맷 감지 | - |
| **OpenAI** | OpenAI API 호환 | `choices[0].delta.content` |
| **Anthropic** | Claude API | `content_block_delta.delta.text` |
| **Gemini** | Google Gemini API | `candidates[].content.parts[].text` |
| **Playground** | JSON Patch 형식 | `op: add/append` |
| **MAS Response** | 멀티에이전트 워크플로우 | `content[].text` + workflow metadata |
| **Custom** | 사용자 정의 JSONPath | 커스텀 추출 규칙 |

### 추가 기능
- 🔐 OAuth 인증 (Google/GitHub)
- 📜 변환 히스토리 저장 (PostgreSQL)
- 🎨 다크 테마 UI
- 📋 원클릭 복사
- 🔄 Auto-detect 포맷 감지

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        Client                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Coolify (PaaS)                            │
│                http://192.168.100.106:8000                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Proxy     │  │  Coolify    │  │  Realtime   │         │
│  │  (Traefik)  │  │   (App)     │  │ (WebSocket) │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐                          │
│  │ PostgreSQL  │  │   Redis     │                          │
│  │    :5432    │  │    :6379    │                          │
│  └─────────────┘  └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

## 📦 기술 스택

| 구성요소 | 기술 | 버전 |
|---------|------|------|
| **Backend** | FastAPI + Uvicorn | 0.128.0 |
| **Database** | PostgreSQL | 16 |
| **ORM** | SQLAlchemy (async) | 2.0 |
| **인증** | Authlib + python-jose | JWT |
| **마이그레이션** | Alembic | 1.18 |
| **배포 플랫폼** | Coolify | 4.0.0-beta.462 |
| **CI/CD** | GitHub Actions | Self-hosted Runner |

## 🖥️ 서버 정보

### Production Server
| 항목 | 값 |
|-----|-----|
| **IP** | `192.168.100.106` |
| **OS** | Ubuntu 24.04 LTS |
| **CPU** | 2 vCPU |
| **RAM** | 8GB |
| **Disk** | 19GB |

### 실행 중인 서비스
```
coolify-proxy      :80, :443, :8080  (Traefik)
coolify            :8000             (Dashboard)
coolify-db         :5432             (PostgreSQL)
coolify-redis      :6379             (Redis)
coolify-realtime   :6001-6002        (WebSocket)
coolify-sentinel                     (Monitoring)
```

### GitHub Actions Runner
- **Name**: `prod-server`
- **Labels**: `self-hosted`, `Linux`, `X64`, `production`
- **Status**: Online

## 🚀 배포 방법

### 1. GitHub Actions (자동 배포)
`main` 브랜치에 push하면 자동 배포됩니다.

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]
```

### 2. Coolify 대시보드
1. http://192.168.100.106:8000 접속
2. 프로젝트 추가 → GitHub 연동
3. 환경변수 설정 후 배포

### 3. 수동 배포
```bash
ssh ubuntu@192.168.100.106
cd /opt/delta-to-json
git pull origin main
docker compose up -d --build
```

## ⚙️ 환경 변수

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/sse_parser
DB_PASSWORD=your_secure_password

# JWT
JWT_SECRET_KEY=your_jwt_secret_here

# OAuth (선택사항)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# App
APP_URL=http://your-domain:8000
```

## 🛠️ 로컬 개발

### 요구사항
- Python 3.12+
- Docker & Docker Compose
- uv (패키지 매니저)

### 설치 및 실행
```bash
# 의존성 설치
uv sync

# 개발 서버 실행
docker compose up -d db
uvicorn main:app --reload

# 또는 Docker로 전체 실행
docker compose up -d
```

### API 엔드포인트
| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 메인 UI |
| POST | `/parse` | SSE 로그 파싱 |
| GET | `/formats` | 지원 포맷 목록 |
| GET | `/health` | 헬스체크 |
| GET | `/auth/google` | Google OAuth |
| GET | `/auth/github` | GitHub OAuth |
| GET | `/history` | 히스토리 목록 |

## 📁 프로젝트 구조

```
delta-to-json/
├── app/
│   ├── auth/           # OAuth 인증
│   │   ├── router.py
│   │   ├── oauth.py
│   │   └── jwt.py
│   ├── history/        # 히스토리 CRUD
│   │   ├── router.py
│   │   └── service.py
│   ├── config.py       # 설정 관리
│   ├── database.py     # DB 연결
│   ├── models.py       # SQLAlchemy 모델
│   └── schemas.py      # Pydantic 스키마
├── migrations/         # Alembic 마이그레이션
├── scripts/            # 배포 스크립트
│   ├── server-setup.sh
│   ├── runner-setup.sh
│   └── deploy.sh
├── templates/
│   └── index.html      # 메인 UI
├── .github/
│   └── workflows/
│       └── deploy.yml  # CI/CD 워크플로우
├── main.py             # FastAPI 앱
├── parser_logic.py     # SSE 파싱 로직
├── docker-compose.yml
├── docker-compose.prod.yml
├── Dockerfile
└── pyproject.toml
```

## 🔧 서버 관리 명령어

### Coolify
```bash
# 상태 확인
docker ps

# 로그 확인
docker logs coolify -f

# 재시작
cd /data/coolify/source && docker compose up -d
```

### GitHub Actions Runner
```bash
# 상태 확인
sudo systemctl status actions.runner.stua1125-delta-to-json.prod-server

# 재시작
sudo systemctl restart actions.runner.stua1125-delta-to-json.prod-server

# 로그
journalctl -u actions.runner.stua1125-delta-to-json.prod-server -f
```

## 🌐 외부 접속 설정 (TODO)

현재 `192.168.100.106`은 사설 IP입니다. 외부 접속을 위해:

1. **Cloudflare Tunnel** (추천)
   - 무료, HTTPS 자동, DDoS 방어
   - `cloudflared` 설치 후 터널 생성

2. **포트포워딩**
   - 라우터에서 8000 포트 개방
   - 공인 IP 필요

3. **Tailscale Funnel**
   - VPN 통합 접근

## 📝 라이선스

MIT License

## 🤝 기여

이슈와 PR을 환영합니다!

---

**Repository**: https://github.com/stua1125/delta-to-json
