name: Daily Manager Routine

on:
  schedule:
    - cron: '30 23 * * *' # 매일 아침 8시 30분 (UTC 23:30)
  workflow_dispatch:      # 수동 실행 버튼

jobs:
  run-manager:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install requests pandas google-generativeai

      - name: Run Daily Script
        run: python daily_manager.py
        env:
          # --- [중요] 아래 항목들이 빠지면 데이터가 비어서 옵니다 ---
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          NAVER_CLIENT_ID: ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
          NAVER_AD_API_KEY: ${{ secrets.NAVER_AD_API_KEY }}
          NAVER_AD_SECRET_KEY: ${{ secrets.NAVER_AD_SECRET_KEY }}
          NAVER_CUSTOMER_ID: ${{ secrets.NAVER_CUSTOMER_ID }}
          APPS_SCRIPT_URL: ${{ secrets.APPS_SCRIPT_URL }}
          APPS_SCRIPT_TOKEN: ${{ secrets.APPS_SCRIPT_TOKEN }}
          # ▼▼▼ 여기가 핵심입니다! ▼▼▼
          DEFAULT_KEYWORDS: ${{ secrets.DEFAULT_KEYWORDS }}
          MY_BRAND_1: ${{ secrets.MY_BRAND_1 }}
          MY_BRAND_2: ${{ secrets.MY_BRAND_2 }}
          COMPETITORS: ${{ secrets.COMPETITORS }}
