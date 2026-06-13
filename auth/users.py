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

# ── 비밀번호 재설정 ───────────────────────────────────────────────────────────
_RESET_ATTEMPTS = {}  # {email: [timestamp, ...]} -- 무차별 대입 방지용 (프로세스 메모리)
_RESET_MAX_PER_HOUR = 3

def _reset_throttled(email):
    """시간당 재설정 시도 횟수 제한"""
    import time as _t
    now = _t.time()
    attempts = [t for t in _RESET_ATTEMPTS.get(email, []) if now - t < 3600]
    _RESET_ATTEMPTS[email] = attempts
    if len(attempts) >= _RESET_MAX_PER_HOUR:
        return True
    attempts.append(now)
    return False

def reset_password(email, display_name=""):
    """본인 확인(가입 시 등록한 이름) 후 임시 비밀번호를 생성해 반환.

    [SECURITY] 이메일만으로 재설정을 허용하면 타인이 이메일 주소만 알아도
    계정을 탈취할 수 있으므로, 가입 시 입력한 이름(display_name)이
    정확히 일치해야만 임시 비밀번호를 발급한다.
    또한 시간당 3회로 시도를 제한해 무차별 대입을 차단한다.
    """
    import random, string
    init_db()
    email = email.strip().lower()
    if not _valid_email(email):
        return False, "이메일 형식이 올바르지 않습니다.", None
    if _reset_throttled(email):
        return False, "재설정 시도가 너무 많습니다. 1시간 후 다시 시도해주세요.", None
    try:
        ws_users = get_users_sheet()
        row, row_num = _find_user_row(ws_users, email)
        # [SECURITY] 계정 존재 여부를 노출하지 않도록 실패 메시지를 통일
        _fail_msg = "입력하신 정보와 일치하는 계정을 찾을 수 없습니다."
        if not row:
            return False, _fail_msg, None
        stored_name = str(row.get("display_name", "") or "").strip()
        if not stored_name or stored_name != display_name.strip():
            log.warning("[users] 비밀번호 재설정 본인확인 실패: %s", email)
            return False, _fail_msg, None
        # 임시 비밀번호 생성 (영문 대소문자 + 숫자 10자리)
        tmp_pw = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        new_hash = _hash_pw(tmp_pw)
        # password_hash 컬럼(3번째, C열) 업데이트
        pw_col_idx = USERS_HEADERS.index("password_hash") + 1  # 1-based
        col_letter = chr(ord("A") + pw_col_idx - 1)
        ws_users.update(f"{col_letter}{row_num}", [[new_hash]], value_input_option="RAW")
        log.info("[users] 비밀번호 재설정: %s", email)
        return True, "임시 비밀번호가 생성됐습니다.", tmp_pw
    except Exception as e:
        log.error("[users] 비밀번호 재설정 오류: %s", e)
        return False, "재설정 중 오류: " + str(e), None

def change_password(email, current_password, new_password):
    """현재 비밀번호 확인 후 새 비밀번호로 변경"""
    init_db()
    email = email.strip().lower()
    ok, msg = _valid_password(new_password)
    if not ok:
        return False, msg
    try:
        ws_users = get_users_sheet()
        row, row_num = _find_user_row(ws_users, email)
        if not row:
            return False, "사용자를 찾을 수 없습니다."
        if not _check_pw(current_password, str(row["password_hash"])):
            return False, "현재 비밀번호가 올바르지 않습니다."
        new_hash = _hash_pw(new_password)
        pw_col_idx = USERS_HEADERS.index("password_hash") + 1
        col_letter = chr(ord("A") + pw_col_idx - 1)
        ws_users.update(f"{col_letter}{row_num}", [[new_hash]], value_input_option="RAW")
        log.info("[users] 비밀번호 변경: %s", email)
        return True, "비밀번호가 변경됐습니다."
    except Exception as e:
        log.error("[users] 비밀번호 변경 오류: %s", e)
        return False, "변경 중 오류: " + str(e)

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
