# -*- coding: utf-8 -*-
"""
Google Sheets DB 연결 및 시트 초기화

Streamlit Secrets (또는 환경변수) 필수 항목:
  GSHEET_SERVICE_ACCOUNT  : Service Account JSON
  GSHEET_ID               : 스프레드시트 ID (URL 의 /d/XXXX/ 부분)

시트 구조:
  users     : id | email | password_hash | display_name | created_at | last_login
  user_keys : user_id | gemini_key | naver_client_id | naver_client_secret |
              naver_ad_api_key | naver_ad_secret_key | naver_customer_id |
              apps_script_url | apps_script_token |
              my_brand_1 | my_brand_2 | competitors | updated_at
"""
import os
import json
import logging

try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GSPREAD_OK = True
except Exception:
    gspread = None
    Credentials = None
    _GSPREAD_OK = False

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

USERS_HEADERS = ["id", "email", "password_hash", "display_name", "created_at", "last_login"]
KEYS_HEADERS  = [
    "user_id", "gemini_key", "naver_client_id", "naver_client_secret",
    "naver_ad_api_key", "naver_ad_secret_key", "naver_customer_id",
    "apps_script_url", "apps_script_token",
    "my_brand_1", "my_brand_2", "competitors",
    "notion_token", "notion_database_id", "slack_webhook_url",
    "updated_at",
]

_client      = None
_spreadsheet = None
_ws_users    = None
_ws_keys     = None


def _load_sa_info():
    sa_info = None

    # 1. Streamlit secrets에서 시도
    try:
        import streamlit as st
        raw = st.secrets.get("GSHEET_SERVICE_ACCOUNT")
        if raw:
            sa_info = dict(raw) if hasattr(raw, "keys") else json.loads(raw)
    except Exception:
        pass

    # 2. 환경변수에서 시도
    if not sa_info:
        raw = os.getenv("GSHEET_SERVICE_ACCOUNT")
        if raw:
            try:
                sa_info = json.loads(raw)
            except json.JSONDecodeError:
                # \n이 실제 줄바꿈으로 저장된 경우 복원 후 재시도
                try:
                    raw2 = raw.replace('\n', '\\n').replace('\\\\n', '\\n')
                    sa_info = json.loads(raw2)
                except Exception:
                    pass

    if not sa_info:
        raise RuntimeError(
            "GSHEET_SERVICE_ACCOUNT 미설정 -- .streamlit/secrets.toml 또는 "
            "환경변수에 Service Account JSON을 설정하세요."
        )
    return sa_info


def _load_spreadsheet_id():
    sheet_id = None
    try:
        import streamlit as st
        sheet_id = st.secrets.get("GSHEET_ID")
    except Exception:
        pass
    if not sheet_id:
        sheet_id = os.getenv("GSHEET_ID")
    if not sheet_id:
        raise RuntimeError(
            "GSHEET_ID 미설정 -- .streamlit/secrets.toml 또는 환경변수에 스프레드시트 ID를 설정하세요."
        )
    return str(sheet_id)


def get_client():
    global _client
    if not _GSPREAD_OK:
        raise RuntimeError("gspread 패키지를 사용할 수 없습니다.")
    if _client is None:
        creds = Credentials.from_service_account_info(_load_sa_info(), scopes=SCOPES)
        _client = gspread.authorize(creds)
        log.info("[db] Google Sheets 클라이언트 초기화 완료")
    return _client


def get_spreadsheet():
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = get_client().open_by_key(_load_spreadsheet_id())
        log.info("[db] 스프레드시트 연결: %s", _spreadsheet.title)
    return _spreadsheet


def get_users_sheet():
    global _ws_users
    if _ws_users is None:
        ss = get_spreadsheet()
        try:
            _ws_users = ss.worksheet("users")
        except gspread.WorksheetNotFound:
            log.info("[db] 'users' 시트 생성")
            _ws_users = ss.add_worksheet(title="users", rows=1000, cols=len(USERS_HEADERS))
            _ws_users.append_row(USERS_HEADERS, value_input_option="RAW")
    return _ws_users


def get_keys_sheet():
    global _ws_keys
    if _ws_keys is None:
        ss = get_spreadsheet()
        try:
            _ws_keys = ss.worksheet("user_keys")
        except gspread.WorksheetNotFound:
            log.info("[db] 'user_keys' 시트 생성")
            _ws_keys = ss.add_worksheet(title="user_keys", rows=1000, cols=len(KEYS_HEADERS))
            _ws_keys.append_row(KEYS_HEADERS, value_input_option="RAW")
    return _ws_keys


def init_db():
    """시트 존재 여부 확인 및 헤더 초기화 (앱 시작 시 1회 호출)"""
    try:
        get_users_sheet()
        get_keys_sheet()
        log.info("[db] Google Sheets DB 초기화 완료")
    except Exception as e:
        log.error("[db] Google Sheets 초기화 오류: %s", e)
        # Railway 환경에서 GSheets 미설정 시 앱 크래시 방지
        pass  # raise 제거
