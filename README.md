# 🛒 nshopping-manager (키워드맵)

네이버 쇼핑 키워드 순위 추적 + SEO/GEO/AEO 마케팅 자동화 플랫폼

드론박스·빛드론의 네이버 쇼핑 노출을 매일 자동 추적하고, 경쟁사 비교 분석,
AI 리포트, SEO 태그·상세페이지 생성까지 지원하는 멀티유저 Streamlit 앱입니다.

## 주요 기능

| 메뉴 | 설명 |
|---|---|
| 📊 Dashboard | 일자별 순위·검색량·점유율 요약 + **시스템 상태 신호등** |
| 📈 순위 추이 | 키워드 × 일자 순위 변동 차트 |
| 🥊 경쟁사 분석 | 1:1 라이벌 비교, 1페이지 점유율, 상위 노출 단어 분석 |
| 🔍 틈새 키워드 | 검색량 대비 경쟁 낮은 키워드 발굴 |
| 🏷️ SEO 태그 생성기 | Gemini 기반 상품명·태그 자동 생성 |
| ⚡ Run & Sync | 수동 크롤 실행 + Google Sheets/Notion 동기화 |
| 🤖 AI Report | Gemini 기반 주간 분석 리포트 |
| 🧭 GEO/AEO 가이드 | AI 검색 최적화 체크리스트 |
| 🤖 AI 인용 추적 | **(신규)** AI에게 구매 추천 질의 → 자사/경쟁사 인용률·언급순서 일자별 추적 (GEO 순위표) |
| 🧩 스키마·FAQ 생성기 | **(신규)** Product/FAQ/HowTo/Breadcrumb JSON-LD 자동 생성 + 리뷰→FAQ 변환 (AEO) |
| ⚖️ GEO 진단 | **(신규)** 자사 vs 경쟁사 상세페이지 6개 신호 상대 평가 + AI 크롤러(robots/llms.txt) 점검 |
| 🧭 키워드 인텐트 | **(신규)** 정보형/비교형/거래형 의도 분류 → 콘텐츠 캘린더 초안 |
| 📅 시즌성 분석 | **(신규)** 데이터랩 검색 추이로 성수기·비수기 파악 → 캠페인 타이밍 추천 |
| 🏢 엔티티 감사 | **(신규)** 채널별 브랜드 정보(NAP·표기) 일관성 점검 + Organization 스키마 생성 |
| 📡 순위 변동 알림 | **(신규)** 급락·TOP3 진입·경쟁사 1p 진입 이벤트 Slack 자동 알림 (Actions 연동) |
| 📄 상세페이지 제작기 | 상품 정보 → HTML 상세페이지 + GEO 준비도 평가 |

## 아키텍처

- **앱**: Streamlit (멀티유저 — 이메일/비밀번호 로그인, bcrypt 해싱)
- **사용자 DB**: Google Sheets (`users`, `user_keys`, `geo_results` 시트)
- **API 키 보안**: 사용자별 키를 Fernet(AES-128)으로 암호화 저장
- **자동 수집**: GitHub Actions (매일 KST 06:00) → 네이버 검색/검색광고 API → Apps Script → Google Sheets
- **알림/동기화**: Slack Webhook, Notion Database

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### 필수 Secrets (.streamlit/secrets.toml 또는 환경변수)

```toml
ENCRYPT_KEY = "Fernet 마스터 키 (운영 필수 — 미설정 시 앱이 기동 거부)"
GSHEET_SERVICE_ACCOUNT = "서비스 계정 JSON"
GSHEET_ID = "스프레드시트 ID"
```

로컬 개발에서만 `DEV_MODE=1` 설정 시 임시 암호화 키 자동 생성이 허용됩니다.

### GitHub Actions Secrets (자동 크롤용)

`NAVER_CLIENT_ID` · `NAVER_CLIENT_SECRET` · `NAVER_AD_API_KEY` ·
`NAVER_AD_SECRET_KEY` · `NAVER_CUSTOMER_ID` · `APPS_SCRIPT_URL` · `APPS_SCRIPT_TOKEN`

선택: `SLACK_WEBHOOK_URL` 설정 시 매일 크롤 직후 순위 변동 이벤트를 Slack으로 알립니다.

## 보안 정책

- 비밀번호: bcrypt 해싱, 평문 저장 없음
- 비밀번호 재설정: 이메일 + 가입 시 등록한 이름 일치 필요, 시간당 3회 제한
- API 키: Fernet 암호화 후 저장 — `ENCRYPT_KEY` 미설정 시 평문 저장 대신 저장 거부
- 세션 토큰 파일(`.auto_tokens.json`)은 `.gitignore`에 포함 — 커밋 금지

## License

Apache-2.0
