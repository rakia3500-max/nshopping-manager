# -*- coding: utf-8 -*-
"""
사용자 인증 및 API 키 관리 (Google Sheets 백엔드)

- register()   : 회원가입 (이메일 중복 확인 + bcrypt 해싱)
- login()      : 로그인 (bcrypt 검증 + last_login 갱신)
- save_keys()  : API 키 저장 (Fernet 암호화)
- load_keys()  : API 키 조회 (Fernet 복호화)
"""
import re
import logging
from datetime import datetime

import hashlib, os as _os
try:
    import bcrypt
    _BCRYPT_OK = True
except Exception:
    bcrypt = None
    _BCRYPT_OK = False

def _hash_pw(password: str) -> str:
    if _BCRYPT_OK:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    salt = _os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"pbkdf2${salt}${h}"

def _check_pw(password: str, stored: str) -> bool:
    if stored.startswith("pbkdf2$"):
        _, salt, h = stored.split("$", 2)
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex() == h
    if _BCRYPT_OK:
        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
    return False

from .db import init_db, get_users_sheet, get_keys_sheet, USERS_HEADERS, KEYS_HEADERS
from .encrypt import encrypt, decrypt

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _valid_email(email):
    return bool(EMAIL_RE.match(email.strip()))

def _valid_password(pw):
    if len(pw) < 8:
        return False, "비밀번호는 8자 이상이어야 합니다."
    return True, ""

def _next_user_id(ws):
    records = ws.get_all_records()
    if not records:
        return 1
    ids = [int(r["id"]) for r in records if str(r.get("id","")).isdigit()]
    return max(ids) + 1 if ids else 1

def _find_user_row(ws, email):
    records = ws.get_all_records()
    for i, r in enumerate(records, start=2):
        if str(r.get("email","")).strip().lower() == email:
            return r, i
    return None, -1

def _find_keys_row(ws, user_id):
    records = ws.get_all_records()
    for i, r in enumerate(records, start=2):
        if str(r.get("user_id","")) == str(user_id):
            return r, i
    return None, -1

# ── 회원가입 ──────────────────────────────────────────────────────────────────
def register(email, password, display_name=""):
    init_db()
    email = email.strip().lower()
    if not _valid_email(email):
        return False, "이메일 형식이 올바르지 않습니다."
    ok, msg = _valid_password(password)
    if not ok:
        return False, msg
    try:
        ws_users = get_users_sheet()
        ws_keys  = get_keys_sheet()
        existing, _ = _find_user_row(ws_users, email)
        if existing:
            return False, "이미 가입된 이메일입니다."
        pw_hash = _hash_pw(password)
        user_id    = _next_user_id(ws_users)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws_users.append_row([user_id, email, pw_hash, display_name.strip(), created_at, ""], value_input_option="RAW")
        empty_keys = [user_id] + [""] * (len(KEYS_HEADERS) - 2) + [created_at]
        ws_keys.append_row(empty_keys, value_input_option="RAW")
        log.info("[users] 회원가입 완료: %s (id=%s)", email, user_id)
        return True, "회원가입이 완료되었습니다. 로그인해 주세요."
    except Exception as e:
        log.error("[users] 회원가입 오류: %s", e)
        return False, "회원가입 중 오류가 발생했습니다: " + str(e)

# ── 로그인 ────────────────────────────────────────────────────────────────────
def login(email, password):
    init_db()
    email = email.strip().lower()
    try:
        ws_users = get_users_sheet()
        row, row_num = _find_user_row(ws_users, email)
        if not row:
            return False, "이메일 또는 비밀번호가 올바르지 않습니다.", None
        if not _check_pw(password, str(row["password_hash"])):
            return False, "이메일 또는 비밀번호가 올바르지 않습니다.", None
        last_login_col = USERS_HEADERS.index("last_login") + 1
        ws_users.update_cell(row_num, last_login_col, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        user = {"id": int(row["id"]), "email": row["email"], "display_name": row.get("display_name", "")}
        log.info("[users] 로그인 성공: %s", email)
        return True, "환영합니다, " + (row.get("display_name") or email) + "!", user
    except Exception as e:
        log.error("[users] 로그인 오류: %s", e)
        return False, "로그인 중 오류가 발생했습니다: " + str(e), None

# ── API 키 저장/조회 ──────────────────────────────────────────────────────────
_KEY_FIELDS = [
    "gemini_key", "naver_client_id", "naver_client_secret",
    "naver_ad_api_key", "naver_ad_secret_key", "naver_customer_id",
    "apps_script_url", "apps_script_token",
    "my_brand_1", "my_brand_2", "competitors",
    "notion_token", "notion_database_id", "slack_webhook_url",
]

def save_keys(user_id, keys):
    try:
        ws_keys = get_keys_sheet()
        _, row_num = _find_keys_row(ws_keys, user_id)
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [str(user_id)] + [encrypt(keys.get(f, "")) for f in _KEY_FIELDS] + [updated_at]
        if row_num == -1:
            ws_keys.append_row(new_row, value_input_option="RAW")
        else:
            end_col = chr(ord("A") + len(KEYS_HEADERS) - 1)
            ws_keys.update("A" + str(row_num) + ":" + end_col + str(row_num), [new_row], value_input_option="RAW")
        log.info("[users] API 키 저장 완료: user_id=%s", user_id)
        return True, "API 키가 저장되었습니다."
    except Exception as e:
        log.error("[users] API 키 저장 오류: %s", e)
        return False, "저장 중 오류: " + str(e)

def load_keys(user_id):
    empty = {f: "" for f in _KEY_FIELDS}
    try:
        init_db()
        ws_keys = get_keys_sheet()
        row, _ = _find_keys_row(ws_keys, user_id)
        if not row:
            return empty
        return {f: decrypt(str(row.get(f, ""))) for f in _KEY_FIELDS}
    except Exception as e:
        log.error("[users] API 키 조회 오류: %s", e)
        return empty
