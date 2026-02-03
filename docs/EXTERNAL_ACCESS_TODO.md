# 외부 네트워크 접속 설정 TODO

현재 서버(`192.168.100.106`)는 사설 네트워크에 있어 VPN 없이는 외부에서 접속할 수 없습니다.
아래 방법 중 하나를 선택하여 외부 접속을 설정하세요.

---

## 📋 방법 비교

| 방법 | 난이도 | 비용 | 보안 | HTTPS | 추천 |
|-----|--------|------|------|-------|------|
| Cloudflare Tunnel | ⭐⭐ | 무료 | ✅ 높음 | ✅ 자동 | ⭐ 추천 |
| Tailscale Funnel | ⭐⭐ | 무료 | ✅ 높음 | ✅ 자동 | |
| ngrok | ⭐ | 유료 | ⚠️ 보통 | ✅ 자동 | |
| 포트포워딩 | ⭐⭐⭐ | 무료 | ⚠️ 주의필요 | ❌ 수동 | |

---

## 🌩️ 방법 1: Cloudflare Tunnel (추천)

### 개요
```
[외부 사용자] → [Cloudflare Edge] → [Tunnel] → [192.168.100.106:8000]
                     ↑
              ✅ HTTPS 자동
              ✅ DDoS 방어
              ✅ Zero Trust 보안
```

### 사전 요구사항
- [ ] Cloudflare 계정 생성 (무료): https://dash.cloudflare.com/sign-up
- [ ] 도메인 보유 (또는 구매)
- [ ] 도메인을 Cloudflare DNS로 이전

### 설정 단계

#### Step 1: 도메인 Cloudflare에 추가
- [ ] Cloudflare 대시보드 → "Add a Site"
- [ ] 도메인 입력 후 DNS 레코드 스캔
- [ ] 도메인 등록업체에서 네임서버를 Cloudflare로 변경
  ```
  네임서버 예시:
  - xxx.ns.cloudflare.com
  - yyy.ns.cloudflare.com
  ```
- [ ] DNS 전파 대기 (최대 24시간, 보통 몇 분)

#### Step 2: Cloudflare Tunnel 생성
- [ ] Cloudflare 대시보드 → Zero Trust → Networks → Tunnels
- [ ] "Create a tunnel" 클릭
- [ ] Tunnel 이름 입력: `delta-to-json-tunnel`
- [ ] Connector 설치 방법에서 **Docker** 선택

#### Step 3: 서버에 cloudflared 설치
```bash
# SSH 접속
ssh ubuntu@192.168.100.106

# cloudflared 설치
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# 버전 확인
cloudflared --version
```
- [ ] cloudflared 설치 완료

#### Step 4: Tunnel 연결
```bash
# Cloudflare 대시보드에서 제공하는 토큰으로 실행
sudo cloudflared service install <YOUR_TUNNEL_TOKEN>

# 서비스 상태 확인
sudo systemctl status cloudflared
```
- [ ] Tunnel 연결 확인 (Cloudflare 대시보드에서 "Healthy" 표시)

#### Step 5: Public Hostname 설정
- [ ] Cloudflare 대시보드 → Tunnels → 생성한 터널 선택
- [ ] "Public Hostnames" 탭 → "Add a public hostname"
- [ ] 설정:
  ```
  Subdomain: app (또는 원하는 이름)
  Domain: your-domain.com
  Service Type: HTTP
  URL: localhost:8000
  ```
- [ ] Coolify 대시보드용 추가 호스트네임:
  ```
  Subdomain: coolify
  Domain: your-domain.com
  Service Type: HTTP
  URL: localhost:8000
  ```

#### Step 6: 접속 테스트
- [ ] https://app.your-domain.com 접속 확인
- [ ] https://coolify.your-domain.com 접속 확인

### 완료 체크리스트
- [ ] Cloudflare 계정 생성
- [ ] 도메인 Cloudflare DNS로 이전
- [ ] Tunnel 생성
- [ ] cloudflared 서버에 설치
- [ ] Tunnel 연결 및 Healthy 확인
- [ ] Public Hostname 설정
- [ ] HTTPS 접속 테스트

---

## 🔗 방법 2: Tailscale Funnel

### 개요
```
[외부 사용자] → [Tailscale Network] → [Funnel] → [192.168.100.106:8000]
                      ↑
               ✅ HTTPS 자동
               ✅ VPN 통합
```

### 사전 요구사항
- [ ] Tailscale 계정 생성: https://tailscale.com
- [ ] Funnel 기능 활성화 (Admin Console에서)

### 설정 단계

#### Step 1: Tailscale 설치
```bash
ssh ubuntu@192.168.100.106

# Tailscale 설치
curl -fsSL https://tailscale.com/install.sh | sh

# 로그인
sudo tailscale up

# 상태 확인
tailscale status
```
- [ ] Tailscale 설치 및 로그인 완료

#### Step 2: Funnel 활성화
```bash
# Admin Console에서 Funnel 허용 필요
# https://login.tailscale.com/admin/acls에서 설정

# Funnel 시작
sudo tailscale funnel 8000
```
- [ ] Funnel 활성화 완료

#### Step 3: 접속 테스트
- [ ] `https://<machine-name>.<tailnet-name>.ts.net` 접속 확인

### 완료 체크리스트
- [ ] Tailscale 계정 생성
- [ ] 서버에 Tailscale 설치
- [ ] Admin Console에서 Funnel 허용
- [ ] Funnel 시작
- [ ] 외부 접속 테스트

---

## 🚇 방법 3: ngrok

### 개요
```
[외부 사용자] → [ngrok Edge] → [Agent] → [192.168.100.106:8000]
                   ↑
            ⚠️ 무료는 URL 변경됨
            💰 고정 URL은 유료
```

### 사전 요구사항
- [ ] ngrok 계정 생성: https://ngrok.com
- [ ] (선택) 유료 플랜 (고정 도메인용)

### 설정 단계

#### Step 1: ngrok 설치
```bash
ssh ubuntu@192.168.100.106

# ngrok 설치
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
  sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
  echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
  sudo tee /etc/apt/sources.list.d/ngrok.list && \
  sudo apt update && sudo apt install ngrok
```
- [ ] ngrok 설치 완료

#### Step 2: 인증 토큰 설정
```bash
# ngrok 대시보드에서 토큰 복사
ngrok config add-authtoken <YOUR_AUTH_TOKEN>
```
- [ ] 인증 토큰 설정 완료

#### Step 3: 터널 시작
```bash
# 일회성 실행
ngrok http 8000

# 또는 백그라운드 실행 (유료 기능)
ngrok http 8000 --domain=your-domain.ngrok.io
```
- [ ] 터널 시작 및 URL 확인

#### Step 4: 서비스로 등록 (선택)
```bash
# systemd 서비스 파일 생성
sudo tee /etc/systemd/system/ngrok.service << EOF
[Unit]
Description=ngrok tunnel
After=network.target

[Service]
ExecStart=/usr/local/bin/ngrok http 8000
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable ngrok
sudo systemctl start ngrok
```
- [ ] 서비스 등록 완료 (선택)

### 완료 체크리스트
- [ ] ngrok 계정 생성
- [ ] ngrok 설치
- [ ] 인증 토큰 설정
- [ ] 터널 시작
- [ ] 외부 접속 테스트

---

## 🔌 방법 4: 포트포워딩

### 개요
```
[외부 사용자] → [공인 IP:8000] → [라우터] → [192.168.100.106:8000]
                    ↑
             ⚠️ 방화벽 설정 필요
             ⚠️ 보안 주의
             ❌ HTTPS 별도 설정
```

### 사전 요구사항
- [ ] 라우터/방화벽 관리자 권한
- [ ] 고정 공인 IP (또는 DDNS)
- [ ] SSL 인증서 (Let's Encrypt 등)

### 설정 단계

#### Step 1: 공인 IP 확인
```bash
curl ifconfig.me
```
- [ ] 공인 IP 확인: `_______________`

#### Step 2: 라우터 포트포워딩 설정
- [ ] 라우터 관리 페이지 접속
- [ ] 포트포워딩 규칙 추가:
  ```
  외부 포트: 8000 (또는 80/443)
  내부 IP: 192.168.100.106
  내부 포트: 8000
  프로토콜: TCP
  ```

#### Step 3: 방화벽 설정 (서버)
```bash
ssh ubuntu@192.168.100.106

# UFW 방화벽 설정
sudo ufw allow 8000/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```
- [ ] 방화벽 규칙 추가 완료

#### Step 4: HTTPS 설정 (선택)
```bash
# Certbot 설치
sudo apt install certbot

# 인증서 발급 (도메인 필요)
sudo certbot certonly --standalone -d your-domain.com
```
- [ ] SSL 인증서 설정 완료 (선택)

#### Step 5: 접속 테스트
- [ ] http://공인IP:8000 접속 확인
- [ ] 외부 네트워크에서 테스트

### 보안 주의사항
- [ ] 불필요한 포트 닫기
- [ ] fail2ban 설치
- [ ] 정기적인 보안 업데이트
- [ ] 강력한 비밀번호 사용

### 완료 체크리스트
- [ ] 공인 IP 확인
- [ ] 라우터 포트포워딩 설정
- [ ] 서버 방화벽 설정
- [ ] (선택) HTTPS 설정
- [ ] 외부 접속 테스트
- [ ] 보안 점검

---

## 📌 권장 순서

1. **개발/테스트용**: ngrok (가장 빠름)
2. **프로덕션용**: Cloudflare Tunnel (가장 안전)
3. **VPN 사용자**: Tailscale Funnel (VPN 통합)
4. **완전한 제어**: 포트포워딩 (전문가용)

---

## ❓ FAQ

### Q: 도메인이 없으면 어떻게 하나요?
A: ngrok 또는 Tailscale Funnel은 자동으로 URL을 제공합니다.

### Q: 무료로 고정 URL을 사용할 수 있나요?
A: Cloudflare Tunnel + 도메인 조합이 가장 경제적입니다.

### Q: 가장 안전한 방법은?
A: Cloudflare Tunnel (Zero Trust 보안 + WAF + DDoS 방어)

### Q: 설정이 가장 쉬운 방법은?
A: ngrok (5분 내 설정 가능)

---

## 🔗 참고 링크

- [Cloudflare Tunnel 문서](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Tailscale Funnel 문서](https://tailscale.com/kb/1223/funnel/)
- [ngrok 문서](https://ngrok.com/docs)
- [Let's Encrypt](https://letsencrypt.org/)
