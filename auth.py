# auth.py
# eski:
# from passlib.context import CryptContext
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# yeni:
from passlib.hash import pbkdf2_sha256
from itsdangerous import TimestampSigner, BadSignature, SignatureExpired
from fastapi import Request

# Parola yardımcıları
def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pbkdf2_sha256.verify(password, password_hash)

# oturum aynı kalsın
SECRET = "change-this-to-a-very-strong-secret"
signer = TimestampSigner(SECRET)
COOKIE_NAME = "session"

def set_session_cookie(response, user_id: int):
    token = signer.sign(str(user_id)).decode("utf-8")
    response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, samesite="lax")

def clear_session_cookie(response):
    response.delete_cookie(COOKIE_NAME)

def get_current_user_id(request: Request) -> int | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        raw = signer.unsign(token, max_age=60*60*24*7)
        return int(raw.decode("utf-8"))
    except (BadSignature, SignatureExpired):
        return None
