# -*- coding: utf-8 -*-
"""사용자 인증 및 API 키 관리 (SQLite 백엔드)"""
import re, logging, hashlib, os as _os
from datetime import datetime
from .db import init_db, _conn
from .encrypt import encrypt, decrypt

log = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

try:
    import bcrypt as _bcrypt; _BCRYPT_OK = True
except Exception:
    _bcrypt = None; _BCRYPT_OK = False

def _hash_pw(pw):
    if _BCRYPT_OK:
        return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()
    salt = _os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 260000).hex()
    return f"pbkdf2${salt}${h}"

def _check_pw(pw, stored):
    if stored.startswith("pbkdf2$"):
        _, salt, h = stored.split("$", 2)
        return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 260000).hex() == h
    if _BCRYPT_OK:
        return _bcrypt.checkpw(pw.encode(), stored.encode())
    return False

_KEY_FIELDS = [
    "gemini_key","naver_client_id","naver_client_secret",
    "naver_ad_api_key","naver_ad_secret_key","naver_customer_id",
    "apps_script_url","apps_script_token",
    "my_brand_1","my_brand_2","competitors",
    "notion_token","notion_database_id","slack_webhook_url",
]

def register(email, password, display_name=""):
    init_db()
    email = email.strip().lower()
    if not EMAIL_RE.match(email): return False, "이메일 형식이 올바르지 않습니다."
    if len(password) < 8: return False, "비밀번호는 8자 이상이어야 합니다."
    try:
        with _conn() as c:
            if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                return False, "이미 가입된 이메일입니다."
            import uuid
            uid = str(uuid.uuid4())[:8]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",
                      (uid, email, _hash_pw(password), display_name.strip(), now, ""))
            c.execute("INSERT OR IGNORE INTO user_keys(user_id) VALUES (?)", (uid,))
        return True, "회원가입이 완료되었습니다. 로그인해 주세요."
    except Exception as e:
        return False, f"오류: {e}"

def login(email, password):
    init_db()
    email = email.strip().lower()
    try:
        with _conn() as c:
            row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not row: return False, "이메일 또는 비밀번호가 올바르지 않습니다.", None
            u = dict(zip(["id","email","password_hash","display_name","created_at","last_login"], row))
            if not _check_pw(password, u["password_hash"]):
                return False, "이메일 또는 비밀번호가 올바르지 않습니다.", None
            c.execute("UPDATE users SET last_login=? WHERE email=?",
                      (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email))
        return True, f"환영합니다, {u.get('display_name') or email}!", \
               {"id": u["id"], "email": u["email"], "display_name": u.get("display_name","")}
    except Exception as e:
        return False, f"로그인 중 오류: {e}", None

def save_keys(user_id, keys):
    try:
        init_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        enc = {f: encrypt(keys.get(f,"")) for f in _KEY_FIELDS}
        with _conn() as c:
            c.execute("INSERT OR REPLACE INTO user_keys VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(user_id),
                 enc["gemini_key"], enc["naver_client_id"], enc["naver_client_secret"],
                 enc["naver_ad_api_key"], enc["naver_ad_secret_key"], enc["naver_customer_id"],
                 enc["apps_script_url"], enc["apps_script_token"],
                 enc["my_brand_1"], enc["my_brand_2"], enc["competitors"],
                 enc["notion_token"], enc["notion_database_id"], enc["slack_webhook_url"],
                 now))
        return True, "API 키가 저장되었습니다."
    except Exception as e:
        return False, f"저장 오류: {e}"

def load_keys(user_id):
    empty = {f:"" for f in _KEY_FIELDS}
    try:
        init_db()
        with _conn() as c:
            row = c.execute("SELECT * FROM user_keys WHERE user_id=?", (str(user_id),)).fetchone()
            if not row: return empty
            cols = ["user_id"] + _KEY_FIELDS + ["updated_at"]
            d = dict(zip(cols, row))
        return {f: decrypt(d.get(f,"")) for f in _KEY_FIELDS}
    except Exception as e:
        log.error("[users] load_keys 오류: %s", e)
        return empty
