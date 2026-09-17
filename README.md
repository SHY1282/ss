# SOXL 구성종목 기여도 대시보드 — Render 배포

## 배포 순서 (약 10분, 무료)

1. **GitHub** (github.com) 계정으로 로그인 → `New repository` → 이름 `soxl-dashboard`, Public 또는 Private → Create.
2. 이 폴더의 4개 파일(`app.py`, `soxl_dashboard.html`, `requirements.txt`, `render.yaml`)을 저장소에 업로드
   (웹에서 `Add file → Upload files` 로 드래그하면 됩니다).
3. **Render** (render.com) 가입 → `New +` → `Blueprint` → 방금 만든 GitHub 저장소 선택 → `Apply`.
   (`render.yaml` 을 읽어 자동으로 설정됩니다. Blueprint 대신 `Web Service` 로 만들 때는
   Build: `pip install -r requirements.txt`, Start: `python app.py`, Plan: Free 로 입력)
4. 2~3분 뒤 `https://soxl-dashboard-xxxx.onrender.com` 주소가 생깁니다. 폰 홈 화면에 추가해 두면 앱처럼 열립니다.

## 알아둘 점

- **무료 플랜은 15분간 접속이 없으면 잠듭니다.** 다시 열면 30초~1분 뒤에 뜹니다(첫 화면에 안내 문구가 나옵니다).
  계속 깨워두고 싶으면 UptimeRobot 같은 무료 모니터링에 `/healthz` 주소를 5분 간격으로 등록하면 됩니다.
- 시세는 Yahoo Finance 를 씁니다. 클라우드 IP 가 차단되는 경우가 간혹 있어 예비로 Finnhub 를 붙여 두었습니다.
  Render 대시보드 → Environment → `FINNHUB_KEY` 에 무료 키(finnhub.io)를 넣으면 Yahoo 실패 시 자동 전환됩니다
  (Finnhub 무료는 거래량이 없어 그 열은 `—` 로 표시).
- 구성종목·비중은 `soxl_dashboard.html` 안의 `RAW` 배열입니다. Direxion 보유내역(https://www.direxion.com/holdings/SOXL.csv)이
  바뀌면 그 부분만 고쳐서 GitHub 에 다시 올리면 Render 가 자동으로 재배포합니다.
- 갱신 주기는 화면에서 15초~2분 중 선택. 서버는 20초 캐시를 두어 여러 기기에서 동시에 열어도 외부 호출이 늘지 않습니다.
