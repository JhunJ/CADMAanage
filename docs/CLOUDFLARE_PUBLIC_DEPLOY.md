# 외부 공개: Cloudflare Tunnel (권장)

`http://172.23.x.x:8000` 같은 **사설 IP**는 인터넷·Cloudflare 엣지에서 라우팅되지 않습니다. 방화벽으로 **80/443 포트를 밖으로 열지 않고** 공개하려면 **Cloudflare Tunnel(`cloudflared`)** 을 쓰면 됩니다.

- 터널 클라이언트가 **사내망에서 아웃바운드(HTTPS)** 로 Cloudflare에 연결합니다.
- 방문자 → Cloudflare → 터널 → `http://127.0.0.1:8000` 또는 `http://172.23.22.63:8000`

전제: Cloudflare에 **`yeobaekstudio.com` 존이 추가**되어 있고, `cadmanager` 같은 호스트 이름을 붙일 수 있어야 합니다.

---

## 1) 터널을 둘 서버 선택

아래 **어느 한 대**면 됩니다.

- `172.23.22.63` **본인(API가 떠 있는 머신)** → 서비스 URL을 `http://127.0.0.1:8000` 으로 두면 됨.
- 같은 사내망의 **별도 Windows/Linux 박스** → `http://172.23.22.63:8000` 으로 프록시.

**요구사항:** 해당 머신에서 `https://*.trycloudflare.com` 등 **Cloudflare로 나가는 HTTPS**가 허용되어 있어야 합니다(프록시·방화벽 예외).

---

## 2) `cloudflared` 설치 (Windows 예시)

1. [Cloudflare Downloads — cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) 에서 Windows용 설치.
2. 설치 후 새 PowerShell에서:

```powershell
cloudflared --version
```

---

## 3) Cloudflare에 로그인(인증서 발급)

한 번만 실행합니다. 브라우저가 뜨면 **터널을 넣을 Zone 권한이 있는 계정**으로 허용합니다.

```powershell
cloudflared tunnel login
```

성공 시 사용자 프로필 폴더에 **인증용 pem** 이 생성됩니다.

---

## 4) 네임드 터널 생성·DNS 연결

```powershell
cloudflared tunnel create cadmanage-prod
```

출력되는 **Tunnel ID**를 메모합니다.

### Public Hostname (대시보드에서 설정 — 가장 단순)

1. Cloudflare 대시보드 → **Zero Trust** → **Networks** → **Tunnels**
2. 방금 만든 터널 선택 → **Public Hostname** 추가
3. 예:
   - **Subdomain:** `cadmanager`
   - **Domain:** `yeobaekstudio.com`
   - **Service type:** HTTP
   - **URL:** `127.0.0.1:8000` (터널이 API와 같은 PC일 때) **또는** `172.23.22.63:8000`

저장하면 Cloudflare가 **DNS(CNAME)** 를 터널에 맞게 잡아 줍니다. **수동으로 A 레코드에 사설 IP를 넣을 필요는 없습니다.**

### CLI로 설정 파일 쓰는 방식

예시는 저장소 `deploy/cloudflared/config.yml.example` 를 참고합니다. Tunnel ID·호스트명·백엔드 URL만 바꾼 뒤:

```powershell
cloudflared tunnel --config "C:\path\to\config.yml" run
```

---

## 5) 서비스로 등록(재부팅 후에도 유지)

Windows는 **작업 스케줄러** 또는 **nssm** 등으로 `cloudflared tunnel run` 을 등록합니다.  
Linux는 [official install as service](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/#set-up-a-tunnel-locally-windows-linux-or-macos) 문서의 systemd 예시를 따릅니다.

---

## 6) SSL/TLS (Cloudflare ↔ 브라우저)

- 터널 + Public Hostname 을 쓰면 방문자는 **HTTPS**로 Cloudflare에 붙습니다.
- Cloudflare 대시보드 → **SSL/TLS** 는 보통 **Full** 이상이면 됩니다(원본이 HTTP인 경우 **Full** 이 일반적).

---

## 7) 앱(FastAPI) 쪽 참고

- 기본 설정으로도 대부분 동작합니다.
- 리다이렉트 URL이 `http`로 잘못 잡히면 `uvicorn` 에 **`--proxy-headers`** 및 **`ForwardedAllowIPS`** (또는 동등 설정) 를 검토합니다.
- **보안:** 공개 후에는 **강한 인증·Rate limit·WAF** 를 Cloudflare에서 검토하세요.

---

## 대안: 공인 IP + VM

사내에 공인 IP와 **NAT 443→앱** 이 가능하고 정책상 허용이면, VM 공인 IP에 A 레코드를 두고 Cloudflare 프록시를 켤 수 있습니다. 다만 **사설 IP만 있는 현재 구조**에는 Tunnel이 가장 빠릅니다.

---

## 요약 체크리스트

| 단계 | 내용 |
|------|------|
| 1 | API가 뜬 머신(또는 같은 망 박스)에 `cloudflared` 설치 |
| 2 | `cloudflared tunnel login` |
| 3 | `cloudflared tunnel create …` 후 Zero Trust에서 Public Hostname → `http://127.0.0.1:8000` 또는 `http://172.23.22.63:8000` |
| 4 | `cadmanager.yeobaekstudio.com` 로 외부에서 접속 테스트 |
| 5 | 터널 프로세스를 서비스로 등록해 상시 기동 |

공식 문서: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
