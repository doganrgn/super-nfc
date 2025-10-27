import os
from typing import Optional

from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from passlib.context import CryptContext

# // CODEx: Çoklu sunucular arasında ortak gizli anahtar kullanıyoruz
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-a-very-strong-secret")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", str(60 * 60 * 24 * 7)))
SECURE_COOKIES = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_signer = TimestampSigner(SECRET_KEY)


def hash_password(password: str) -> str:
    # // CODEx: Parolaları bcrypt ile güvenle saklıyoruz
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def set_session_cookie(response, user_id: int) -> None:
    # // CODEx: Oturum çerezini imzalı ve süreli olarak ayarlıyoruz
    token = _signer.sign(str(user_id)).decode("utf-8")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIES,
        max_age=SESSION_MAX_AGE,
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def get_current_user_id(request: Request) -> Optional[int]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        raw = _signer.unsign(token, max_age=SESSION_MAX_AGE)
        return int(raw.decode("utf-8"))
    except (BadSignature, SignatureExpired):
        return None
