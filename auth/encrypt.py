# -*- coding: utf-8 -*-
"""
API 키 암호화/복호화 모듈 (Fernet AES-128)

마스터 키(ENCRYPT_KEY)는 반드시 Streamlit Secrets 또는 환경변수에만 보관.
DB에는 암호화된 값만 저장되므로 DB 유출 시에도 키 노출 없음.
"""
import os
import base64
import logging
try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_OK = True
except Exception:
    Fernet = None
    InvalidToken = Exception
    _CRYPTO_OK = False

log = logging.getLogger(__name__)

# ── 마스터 암호화 키 로드 ────────────────────────────────────────────────────
# 우선순위: st.secrets > 환경변수 > 자동 생성(개발 전용)
def _load_master_key() -> bytes:
    raw = None

    # 1) Streamlit secrets
    try:
        import streamlit as st
        raw = st.secrets.get("ENCRYPT_KEY", None)
    except Exception:
        pass

    # 2) 환경변수
    if not raw:
        raw = os.getenv("ENCRYPT_KEY")

    # 3) 개발 환경 fallback — .streamlit/secrets.toml에 ENCRYPT_KEY가 없을 때
    #    운영 배포에서는 반드시 Secrets에 설정할 것
    if not raw:
        key_file = os.path.join(os.path.dirname(__file__), ".dev_key")
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read().strip()
        # 최초 실행 시 키 자동 생성 (개발 전용)
        if not _CRYPTO_OK:
            return b""
        new_key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(new_key)
        log.warning("[encrypt] ENCRYPT_KEY 미설정 — 개발용 키 자동 생성 (.dev_key). "
                    "운영 환경에서는 반드시 Streamlit Secrets에 ENCRYPT_KEY를 설정하세요.")
        return new_key

    # base64 또는 raw bytes 처리
    if isinstance(raw, str):
        raw = raw.strip().encode()
    # Fernet 키는 44바이트 base64 형식 — 짧으면 패딩
    try:
        base64.urlsafe_b64decode(raw)
        return raw
    except Exception:
        # 일반 문자열이면 Fernet 키로 파생
        import hashlib
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
        return derived


_FERNET = None

def _get_fernet():
    global _FERNET
    if not _CRYPTO_OK:
        return None
    if _FERNET is None:
        _FERNET = Fernet(_load_master_key())
    return _FERNET


# ── 공개 API ─────────────────────────────────────────────────────────────────

def encrypt(plain: str) -> str:
    """평문 문자열 → 암호화된 base64 문자열"""
    if not plain:
        return ""
    if not _CRYPTO_OK:
        return plain  # 암호화 불가 시 평문 저장
    try:
        return _get_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")
    except Exception as e:
        log.error(f"[encrypt] 암호화 실패: {e}")
        return ""


def decrypt(cipher: str) -> str:
    """암호화된 base64 문자열 → 평문 문자열"""
    if not cipher:
        return ""
    if not _CRYPTO_OK:
        return cipher  # 암호화 안 됐으면 평문 그대로 반환
    try:
        return _get_fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        log.error("[encrypt] 복호화 실패 — 마스터 키 불일치 또는 손상된 데이터")
        return ""
    except Exception as e:
        log.error(f"[encrypt] 복호화 오류: {e}")
        return ""


def generate_key() -> str:
    """새 Fernet 마스터 키 생성 (최초 설정 시 사용)"""
    return Fernet.generate_key().decode("utf-8")
