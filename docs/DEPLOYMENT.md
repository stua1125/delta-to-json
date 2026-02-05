# SSE Delta Log Aggregator - 배포 가이드

프라이빗 VM에 도메인으로 배포하는 방법을 설명합니다.

## 목차

1. [사전 요구사항](#사전-요구사항)
2. [VM 초기 설정](#vm-초기-설정)
3. [프로젝트 배포](#프로젝트-배포)
4. [Nginx 리버스 프록시 설정](#nginx-리버스-프록시-설정)
5. [SSL 인증서 설정](#ssl-인증서-설정)
6. [서비스 관리](#서비스-관리)
7. [문제 해결](#문제-해결)

---

## 사전 요구사항

### VM 요구사항
- Ubuntu 20.04+ 또는 Debian 11+
- 최소 1GB RAM, 10GB 디스크
- 공인 IP 또는 내부 네트워크 IP
- SSH 접근 가능

### 도메인 설정 (선택)
- 도메인이 있다면 A 레코드를 VM IP로 설정
- 내부망 전용이라면 `/etc/hosts` 또는 내부 DNS 사용

---

## VM 초기 설정

### 1. SSH 접속

```bash
ssh ubuntu@192.168.100.106
```

### 2. 시스템 업데이트

```bash
sudo apt update && sudo apt upgrade -y
```

### 3. Docker 설치

```bash
# Docker 설치
curl -fsSL https://get.docker.com | sh

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 변경사항 적용 (재로그인 또는)
newgrp docker

# 설치 확인
docker --version
docker compose version
```

### 4. Git 설치 (없는 경우)

```bash
sudo apt install git -y
```

---

## 프로젝트 배포

### 1. 프로젝트 클론

```bash
cd ~
git clone https://github.com/stua1125/delta-to-json.git
cd delta-to-json
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
cat > .env << 'EOF'
# Database
DB_PASSWORD=your-secure-password-here

# JWT Secret (보안을 위해 랜덤 문자열 사용)
# 생성 방법: openssl rand -hex 32
JWT_SECRET_KEY=change-this-to-random-string

# App URL (도메인 또는 IP)
APP_URL=http://192.168.100.106:8000

# OAuth (선택사항)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
EOF

# 파일 권한 설정
chmod 600 .env
```

### 3. Docker 이미지 빌드 및 실행

```bash
# 프로덕션 설정으로 빌드 및 실행
docker compose -f docker-compose.prod.yml up -d --build

# 또는 개발용 설정으로 실행
docker compose up -d --build

# 로그 확인
docker compose logs -f
```

### 4. 서비스 확인

```bash
# 컨테이너 상태 확인
docker compose ps

# 헬스체크
curl http://localhost:8000/health

# 웹 접속 테스트
curl http://localhost:8000
```

---

## Nginx 리버스 프록시 설정

도메인 사용 또는 SSL이 필요한 경우 Nginx를 설정합니다.

### 1. Nginx 설치

```bash
sudo apt install nginx -y
```

### 2. 사이트 설정 생성

```bash
sudo tee /etc/nginx/sites-available/delta-to-json << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 또는 _ 로 모든 요청 수락

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
}
EOF
```

### 3. 설정 활성화

```bash
# 심볼릭 링크 생성
sudo ln -sf /etc/nginx/sites-available/delta-to-json /etc/nginx/sites-enabled/

# 기본 설정 제거 (선택)
sudo rm -f /etc/nginx/sites-enabled/default

# 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl reload nginx
sudo systemctl enable nginx
```

---

## SSL 인증서 설정

### Let's Encrypt (공인 도메인용)

```bash
# Certbot 설치
sudo apt install certbot python3-certbot-nginx -y

# 인증서 발급 및 자동 설정
sudo certbot --nginx -d your-domain.com

# 자동 갱신 테스트
sudo certbot renew --dry-run
```

### 자체 서명 인증서 (내부망용)

```bash
# 인증서 디렉토리 생성
sudo mkdir -p /etc/nginx/ssl

# 자체 서명 인증서 생성
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/selfsigned.key \
  -out /etc/nginx/ssl/selfsigned.crt \
  -subj "/CN=192.168.100.106"

# Nginx SSL 설정 추가
sudo tee /etc/nginx/sites-available/delta-to-json << 'EOF'
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/ssl/selfsigned.crt;
    ssl_certificate_key /etc/nginx/ssl/selfsigned.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo nginx -t && sudo systemctl reload nginx
```

---

## 서비스 관리

### 서비스 시작/중지

```bash
# 시작
docker compose -f docker-compose.prod.yml up -d

# 중지
docker compose -f docker-compose.prod.yml down

# 재시작
docker compose -f docker-compose.prod.yml restart

# 로그 확인
docker compose -f docker-compose.prod.yml logs -f app
```

### 업데이트 배포

```bash
cd ~/delta-to-json

# 최신 코드 가져오기
git pull origin main

# 이미지 재빌드 및 재시작
docker compose -f docker-compose.prod.yml up -d --build

# 이전 이미지 정리
docker image prune -f
```

### 데이터베이스 백업

```bash
# 백업
docker compose exec db pg_dump -U postgres sse_parser > backup_$(date +%Y%m%d).sql

# 복원
cat backup_20240101.sql | docker compose exec -T db psql -U postgres sse_parser
```

---

## 문제 해결

### 컨테이너가 시작되지 않음

```bash
# 로그 확인
docker compose logs app
docker compose logs db

# 컨테이너 상태 확인
docker compose ps -a
```

### 데이터베이스 연결 실패

```bash
# DB 컨테이너 상태 확인
docker compose exec db pg_isready -U postgres

# 연결 테스트
docker compose exec db psql -U postgres -d sse_parser -c "SELECT 1;"
```

### 포트 충돌

```bash
# 사용 중인 포트 확인
sudo lsof -i :8000
sudo lsof -i :5432

# 프로세스 종료
sudo kill -9 <PID>
```

### 디스크 공간 부족

```bash
# Docker 리소스 정리
docker system prune -a --volumes
```

---

## 빠른 배포 스크립트

한 번에 배포하려면 아래 스크립트를 사용하세요:

```bash
#!/bin/bash
# deploy.sh

set -e

echo "==> Pulling latest code..."
git pull origin main

echo "==> Building and starting containers..."
docker compose -f docker-compose.prod.yml up -d --build

echo "==> Waiting for services..."
sleep 10

echo "==> Health check..."
curl -f http://localhost:8000/health || echo "Health check failed"

echo "==> Cleaning up..."
docker image prune -f

echo "==> Deployment complete!"
docker compose ps
```

```bash
chmod +x deploy.sh
./deploy.sh
```

---

## 접속 정보

- **웹 UI**: http://192.168.100.106:8000
- **API 문서**: http://192.168.100.106:8000/docs
- **헬스체크**: http://192.168.100.106:8000/health
