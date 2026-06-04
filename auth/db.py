# -*- coding: utf-8 -*-
"""SQLite 기반 로컬 DB (Google Sheets 불필요)"""
import os
import sqlite3
import logging

log = logging.getLogger(__name__)

_AUTH_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH  = os.path.join(_AUTH_DIR, "..", "users.db")

def _conn():
    return sqlite3.connect(_DB_PATH, check_same_thread=False)

def init_db():
    try:
        with _conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT,
                created_at TEXT,
                last_login TEXT
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS user_keys (
                user_id TEXT PRIMARY KEY,
                gemini_key TEXT, naver_client_id TEXT, naver_client_secret TEXT,
                naver_ad_api_key TEXT, naver_ad_secret_key TEXT, naver_customer_id TEXT,
                apps_script_url TEXT, apps_script_token TEXT,
                my_brand_1 TEXT, my_brand_2 TEXT, competitors TEXT,
                notion_token TEXT, notion_database_id TEXT, slack_webhook_url TEXT,
                updated_at TEXT
            )""")
        log.info("[db] SQLite DB 초기화 완료: %s", _DB_PATH)
    except Exception as e:
        log.error("[db] 초기화 오류: %s", e)

def get_users_sheet():
    """users 테이블 래퍼 (호환성 유지)"""
    return _conn()

def get_keys_sheet():
    """user_keys 테이블 래퍼 (호환성 유지)"""
    return _conn()
