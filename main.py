import csv
import io
import os
import secrets
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI
from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.sql import func
from sqlmodel import select

import qrcode
from qrcode.image.pil import PilImage

from auth import (
    SECRET_KEY,
    clear_session_cookie,
    get_current_user_id,
    hash_password,
    set_session_cookie,
    verify_password,
)
from db import Click, Profile, Tag, User, get_session, init_db

# // CODEx: Konfigürasyon değerlerini merkezi hale getiriyoruz
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
PURCHASE_URL = os.getenv("PURCHASE_URL", "https://satin-al.example.com")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "destek@example.com")
_admin_defaults = {"doganrgn@gmail.com"}
ADMIN_EMAILS = {
    email.strip() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip()
} or _admin_defaults

# // CODEx: Auth modülündeki SECRET_KEY'in yüklendiğini doğruluyoruz
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be defined for session güvenliği")

# // CODEx: FastAPI uygulaması ve şablon motoru kurulumu
app = FastAPI()
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def render_template(
    request: Request, template_name: str, context: Optional[Dict] = None, status_code: int = 200
) -> HTMLResponse:
    # // CODEx: Şablon isimlerini parametre olarak alan yardımcı fonksiyon
    payload = {
        "request": request,
        "user_id": get_current_user_id(request),
        "SUPPORT_EMAIL": SUPPORT_EMAIL,
        "PURCHASE_URL": PURCHASE_URL,
    }
    if context:
        payload.update(context)
    return templates.TemplateResponse(template_name, payload, status_code=status_code)


@app.on_event("startup")
def on_startup() -> None:
    # // CODEx: Uygulama başlarken veritabanını ve kolonları doğruluyoruz
    init_db()


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


def _sanitize_next(url_value: Optional[str]) -> str:
    # // CODEx: Açık yönlendirme riskini engelliyoruz
    if not url_value:
        return "/dashboard"
    url_value = url_value.strip()
    if not url_value.startswith("/"):
        return "/dashboard"
    return url_value


def _load_user(user_id: Optional[int]) -> Optional[User]:
    if not user_id:
        return None
    with get_session() as session:
        return session.get(User, user_id)


def _ensure_admin(user: User) -> None:
    # // CODEx: Admin kontrolleri için yardımcı fonksiyon
    if user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render_template(
        request,
        "home.html",
        {
            "title": "Super NFC Dashboard",
            "purchase_url": PURCHASE_URL,
        },
    )


@app.get("/register", response_class=HTMLResponse)
def register_form(
    request: Request,
    pending_shortid: Optional[str] = None,
    next: Optional[str] = None,
    error: Optional[str] = None,
):
    # // CODEx: NFC taraması yapılmadan kayıt olunmaması için kontrol
    if not pending_shortid:
        error = error or "Kayıt için önce NFC etiketinizi okutmalısınız."
    return render_template(
        request,
        "register.html",
        {
            "pending_shortid": pending_shortid,
            "next_url": _sanitize_next(next),
            "error": error,
        },
    )


@app.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    name: Optional[str] = Form(None),
    pending_shortid: str = Form(""),
    next_url: str = Form("/dashboard"),
):
    email = email.strip().lower()
    pending_shortid = pending_shortid.strip()
    if not pending_shortid:
        return register_form(
            request,
            pending_shortid=None,
            next=next_url,
            error="NFC etiketini okutmadan kayıt olamazsınız.",
        )

    with get_session() as session:
        existing_user = session.exec(select(User).where(User.email == email)).first()
        if existing_user:
            return register_form(
                request,
                pending_shortid=pending_shortid,
                next=next_url,
                error="Bu e-posta zaten kayıtlı. Lütfen giriş yapın.",
            )

        tag = session.exec(select(Tag).where(Tag.shortid == pending_shortid)).first()
        if not tag:
            return register_form(
                request,
                pending_shortid=None,
                next=next_url,
                error="Bu shortid sistemde bulunamadı. Lütfen önce etiketi envantere ekleyin.",
            )
        if tag.owner_user_id is not None:
            return register_form(
                request,
                pending_shortid=None,
                next=next_url,
                error="Bu etiket zaten başka bir kullanıcıya atanmış.",
            )

        user = User(email=email, password_hash=hash_password(password), name=name)
        session.add(user)
        session.commit()
        session.refresh(user)

        tag.owner_user_id = user.id
        session.add(tag)

        profile = session.exec(select(Profile).where(Profile.tag_id == tag.id)).first()
        if not profile:
            profile = Profile(tag_id=tag.id)
            session.add(profile)
        session.commit()

    destination = _sanitize_next(next_url) or f"/claim/{pending_shortid}"
    if destination == "/dashboard":
        destination = f"/claim/{pending_shortid}"
    response = RedirectResponse(url=destination, status_code=303)
    set_session_cookie(response, user.id)  # type: ignore[name-defined]
    return response


@app.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    e: Optional[str] = None,
    next: Optional[str] = None,
):
    error = None
    if e == "exists":
        error = "Bu e-posta zaten kayıtlı. Lütfen giriş yapın."
    elif e == "invalid":
        error = "E-posta veya parola hatalı."
    return render_template(
        request,
        "login.html",
        {"error": error, "next_url": _sanitize_next(next)},
    )


@app.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/dashboard"),
):
    email = email.strip().lower()
    with get_session() as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user or not verify_password(password, user.password_hash):
            return RedirectResponse(url="/login?e=invalid", status_code=303)

    destination = _sanitize_next(next_url)
    response = RedirectResponse(url=destination, status_code=303)
    set_session_cookie(response, user.id)
    return response


@app.post("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(response)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    with get_session() as session:
        tags = session.exec(select(Tag).where(Tag.owner_user_id == user_id).order_by(Tag.created_at)).all()
        tag_cards = []
        for tag in tags:
            count_result = session.exec(select(func.count(Click.id)).where(Click.tag_id == tag.id)).first()
            click_count = int(count_result or 0)
            tag_cards.append(
                {
                    "shortid": tag.shortid,
                    "count": int(click_count or 0),
                    "created_at": tag.created_at,
                }
            )
        user = session.get(User, user_id)
    is_admin = bool(user and user.email in ADMIN_EMAILS)

    return render_template(
        request,
        "dashboard.html",
        {
            "tags": tag_cards,
            "is_admin": is_admin,
        },
    )


@app.get("/claim-info/{shortid}", response_class=HTMLResponse)
def claim_info(request: Request, shortid: str):
    with get_session() as session:
        tag = session.exec(select(Tag).where(Tag.shortid == shortid)).first()
    if not tag:
        return render_template(
            request,
            "tag_404.html",
            {
                "shortid": shortid,
                "purchase_url": PURCHASE_URL,
                "support_email": SUPPORT_EMAIL,
            },
            status_code=404,
        )

    if tag.owner_user_id:
        owner = _load_user(tag.owner_user_id)
        is_owner = tag.owner_user_id == get_current_user_id(request)
        return render_template(
            request,
            "claim_info.html",
            {
                "shortid": shortid,
                "logged_in": bool(get_current_user_id(request)),
                "already_claimed": True,
                "owner_email": owner.email if owner else None,
                "support_email": SUPPORT_EMAIL,
                "is_owner": is_owner,
                "edit_url": f"/edit/{shortid}" if is_owner else None,
            },
        )

    login_target = f"/login?next=/claim/{shortid}"
    register_target = f"/register?pending_shortid={shortid}&next=/claim/{shortid}"
    return render_template(
        request,
        "claim_info.html",
        {
            "shortid": shortid,
            "logged_in": bool(get_current_user_id(request)),
            "login_url": login_target,
            "register_url": register_target,
            "already_claimed": False,
            "support_email": SUPPORT_EMAIL,
        },
    )


@app.get("/claim/{shortid}", response_class=HTMLResponse)
def claim_form(request: Request, shortid: str):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url=f"/login?next=/claim/{shortid}", status_code=303)

    with get_session() as session:
        tag = session.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag bulunamadı")
        if tag.owner_user_id and tag.owner_user_id != user_id:
            raise HTTPException(status_code=403, detail="Bu tag başka bir kullanıcıya ait")
        if tag.owner_user_id == user_id:
            return RedirectResponse(url=f"/edit/{shortid}", status_code=303)

    return render_template(
        request,
        "claim.html",
        {"shortid": shortid, "error": None},
    )


@app.post("/claim/{shortid}")
def claim_submit(request: Request, shortid: str):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url=f"/login?next=/claim/{shortid}", status_code=303)

    with get_session() as session:
        tag = session.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag bulunamadı")
        if tag.owner_user_id and tag.owner_user_id != user_id:
            return render_template(
                request,
                "claim.html",
                {"shortid": shortid, "error": "Bu tag başka bir kullanıcıya atanmış."},
            )
        tag.owner_user_id = user_id
        session.add(tag)
        profile = session.exec(select(Profile).where(Profile.tag_id == tag.id)).first()
        if not profile:
            profile = Profile(tag_id=tag.id)
            session.add(profile)
        session.commit()

    return RedirectResponse(url=f"/edit/{shortid}", status_code=303)


@app.get("/t/{shortid}", response_class=HTMLResponse)
def show_tag(request: Request, shortid: str):
    with get_session() as session:
        tag = session.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            return render_template(
                request,
                "tag_404.html",
                {
                    "shortid": shortid,
                    "purchase_url": PURCHASE_URL,
                    "support_email": SUPPORT_EMAIL,
                },
                status_code=404,
            )
        if not tag.owner_user_id:
            return RedirectResponse(url=f"/claim-info/{shortid}", status_code=303)

        profile = session.exec(select(Profile).where(Profile.tag_id == tag.id)).first()
        try:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent")
            session.add(Click(tag_id=tag.id, ip=ip, ua=ua))
            session.commit()
        except Exception:
            session.rollback()
        profile_data = None
        if profile:
            profile_data = {
                "full_name": profile.full_name,
                "title": profile.title,
                "description": profile.description,
                "link": profile.link,
                "image_url": profile.image_url,
                "phone": profile.phone,
                "public_email": profile.public_email,
                "instagram": profile.instagram,
                "linkedin": profile.linkedin,
                "facebook": profile.facebook,
                "whatsapp": profile.whatsapp,
                "iban": profile.iban,
                "theme_color": profile.theme_color,
            }

    return render_template(
        request,
        "tag.html",
        {"tag_id": shortid, "profile": profile_data},
    )


@app.get("/edit/{shortid}", response_class=HTMLResponse)
def edit_form(request: Request, shortid: str):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    with get_session() as session:
        tag = session.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag or tag.owner_user_id != user_id:
            raise HTTPException(status_code=404, detail="Tag bulunamadı")
        profile = session.exec(select(Profile).where(Profile.tag_id == tag.id)).first()
        if not profile:
            profile = Profile(tag_id=tag.id)
            session.add(profile)
            session.commit()
            session.refresh(profile)

    return render_template(
        request,
        "edit.html",
        {
            "tag_id": shortid,
            "profile": profile,
        },
    )


@app.post("/edit/{shortid}")
async def edit_submit(
    request: Request,
    shortid: str,
    full_name: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
    link: str = Form(""),
    phone: str = Form(""),
    public_email: str = Form(""),
    instagram: str = Form(""),
    linkedin: str = Form(""),
    facebook: str = Form(""),
    whatsapp: str = Form(""),
    iban: str = Form(""),
    theme_color: str = Form("#2563eb"),
    image: UploadFile | None = File(None),
):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    with get_session() as session:
        tag = session.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag or tag.owner_user_id != user_id:
            raise HTTPException(status_code=404, detail="Tag bulunamadı")
        profile = session.exec(select(Profile).where(Profile.tag_id == tag.id)).first()
        if not profile:
            profile = Profile(tag_id=tag.id)
            session.add(profile)
            session.commit()
            session.refresh(profile)

        if image and image.filename:
            ext = os.path.splitext(image.filename)[1].lower()
            if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                ext = ".jpg"
            safe_name = f"{shortid}{ext}"
            dest = UPLOAD_DIR / safe_name
            content = await image.read()
            with dest.open("wb") as output:
                output.write(content)
            profile.image_url = f"/uploads/{safe_name}"

        instagram_value = instagram.strip()
        if instagram_value and not instagram_value.startswith("http"):
            instagram_value = instagram_value.lstrip("@")
            instagram_value = f"https://instagram.com/{instagram_value}"
        linkedin_value = linkedin.strip()
        if linkedin_value and not linkedin_value.startswith("http"):
            linkedin_value = linkedin_value.lstrip("@")
            if linkedin_value.startswith("/in/"):
                linkedin_value = f"https://www.linkedin.com{linkedin_value}"
            else:
                linkedin_value = f"https://www.linkedin.com/in/{linkedin_value}"
        facebook_value = facebook.strip()
        if facebook_value and not facebook_value.startswith("http"):
            facebook_value = facebook_value.lstrip("@")
            facebook_value = f"https://facebook.com/{facebook_value}"
        link_value = link.strip()
        if link_value and not link_value.startswith("http"):
            link_value = f"https://{link_value}"
        whatsapp_value = whatsapp.strip().replace(" ", "")
        iban_value = iban.strip().replace(" ", "")

        profile.full_name = full_name.strip() or None
        profile.title = title.strip() or None
        profile.description = description.strip() or None
        profile.link = link_value or None
        profile.phone = phone.strip() or None
        profile.public_email = public_email.strip() or None
        profile.instagram = instagram_value or None
        profile.linkedin = linkedin_value or None
        profile.facebook = facebook_value or None
        profile.whatsapp = whatsapp_value or None
        profile.iban = iban_value or None

        theme_value = theme_color.strip()
        if theme_value and theme_value.startswith("#") and len(theme_value) in {4, 7}:
            profile.theme_color = theme_value
        profile.updated_at = datetime.utcnow()

        session.add(profile)
        session.commit()

    return RedirectResponse(url=f"/t/{shortid}", status_code=303)


def generate_shortid(length: int = 8) -> str:
    # // CODEx: Admin'in ürettiği shortid'lerin benzersiz olmasını sağlıyoruz
    token = secrets.token_urlsafe(length)
    return token.replace("-", "").replace("_", "")[:length]


@app.post("/admin/generate")
def admin_generate(request: Request, n: int = Form(10)):
    user = _load_user(get_current_user_id(request))
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    _ensure_admin(user)

    created: List[str] = []
    n = max(1, min(int(n), 1000))
    with get_session() as session:
        for _ in range(n):
            candidate = generate_shortid(8)
            while session.exec(select(Tag).where(Tag.shortid == candidate)).first():
                candidate = generate_shortid(8)
            session.add(Tag(shortid=candidate))
            session.commit()
            created.append(candidate)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["shortid"])
    for sid in created:
        writer.writerow([sid])
    buffer.seek(0)

    output = io.BytesIO(buffer.getvalue().encode("utf-8"))
    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=generated_tags.csv"}
    return StreamingResponse(output, media_type="text/csv", headers=headers)


@app.get("/admin/unassigned", response_class=HTMLResponse)
def admin_unassigned(request: Request):
    user = _load_user(get_current_user_id(request))
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    _ensure_admin(user)

    with get_session() as session:
        tags = session.exec(select(Tag).where(Tag.owner_user_id.is_(None)).order_by(Tag.created_at.desc())).all()

    return render_template(
        request,
        "admin_unassigned.html",
        {"tags": tags},
    )


@app.post("/admin/inventory_import")
def admin_inventory_import(request: Request, csv_text: str = Form("")):
    user = _load_user(get_current_user_id(request))
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    _ensure_admin(user)

    rows = [row.strip() for row in csv_text.splitlines() if row.strip()]
    created = 0
    skipped = 0
    with get_session() as session:
        for row in rows:
            candidate = row.split(",")[0].strip()
            if not candidate:
                continue
            exists = session.exec(select(Tag).where(Tag.shortid == candidate)).first()
            if exists:
                skipped += 1
                continue
            session.add(Tag(shortid=candidate))
            session.commit()
            created += 1
    return RedirectResponse(
        url=f"/admin/unassigned?import_ok={created}&skip={skipped}",
        status_code=303,
    )


@app.post("/admin/qrzip")
def admin_qr_zip(
    request: Request,
    ids: str = Form(""),
    size: int = Form(10),
    border: int = Form(4),
):
    user = _load_user(get_current_user_id(request))
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    _ensure_admin(user)

    raw = ids.replace(",", " ").split()
    if not raw:
        raise HTTPException(status_code=400, detail="ID listesi boş")

    with get_session() as session:
        valid_ids = [sid for sid in raw if session.exec(select(Tag).where(Tag.shortid == sid)).first()]
    if not valid_ids:
        raise HTTPException(status_code=400, detail="Geçerli shortid bulunamadı")

    memory = io.BytesIO()
    with zipfile.ZipFile(memory, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for sid in valid_ids:
            url = f"{PUBLIC_BASE_URL.rstrip('/')}/t/{sid}" if PUBLIC_BASE_URL else f"/t/{sid}"
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_Q,
                box_size=max(1, min(int(size), 20)),
                border=max(1, min(int(border), 10)),
            )
            qr.add_data(url)
            qr.make(True)
            img: PilImage = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            archive.writestr(f"qr_{sid}.png", buf.getvalue())
    memory.seek(0)
    headers = {"Content-Disposition": "attachment; filename=qr_bulk.zip"}
    return StreamingResponse(memory, media_type="application/zip", headers=headers)


@app.get("/qr/{shortid}")
def qr_code(shortid: str, size: int = 10, border: int = 4):
    with get_session() as session:
        tag = session.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag bulunamadı")

    target_url = f"{PUBLIC_BASE_URL.rstrip('/')}/t/{shortid}" if PUBLIC_BASE_URL else f"/t/{shortid}"
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=max(1, min(int(size), 20)),
        border=max(1, min(int(border), 10)),
    )
    qr.add_data(target_url)
    qr.make(True)
    img: PilImage = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    headers = {"Content-Disposition": f'inline; filename="qr_{shortid}.png"'}
    return StreamingResponse(buf, media_type="image/png", headers=headers)


@app.get("/api/options")
def api_options(request: Request) -> Dict:
    user_id = get_current_user_id(request)
    if not user_id:
        return {
            "role": "guest",
            "sections": [
                {
                    "title": "Hoş Geldin",
                    "items": [
                        {"name": "Giriş Yap", "url": "/login", "icon": "box-arrow-in-right"},
                        {"name": "Tag Satın Al", "url": PURCHASE_URL, "icon": "bag"},
                    ],
                }
            ],
        }

    with get_session() as session:
        user = session.get(User, user_id)
        tags = session.exec(select(Tag).where(Tag.owner_user_id == user_id).order_by(Tag.created_at)).all()
    is_admin = bool(user and user.email in ADMIN_EMAILS)

    sections: List[Dict] = [
        {
            "title": "Hızlı İşlemler",
            "items": [
                {"name": "Kontrol Paneli", "url": "/dashboard", "icon": "speedometer2"},
            ],
        }
    ]

    for tag in tags:
        sections.append(
            {
                "title": f"Tag {tag.shortid}",
                "items": [
                    {"name": "Profili Gör", "url": f"/t/{tag.shortid}", "icon": "person-badge"},
                    {"name": "Profili Düzenle", "url": f"/edit/{tag.shortid}", "icon": "pencil-square"},
                    {"name": "İstatistikler", "url": f"/stats/{tag.shortid}", "icon": "graph-up"},
                    {"name": "QR Kod", "url": f"/qr/{tag.shortid}", "icon": "qr-code"},
                ],
            }
        )

    if is_admin:
        sections.append(
            {
                "title": "Admin Paneli",
                "items": [
                    {"name": "Boş Tag’ler", "url": "/admin/unassigned", "icon": "card-list"},
                    {"name": "CSV Envanter", "url": "/admin/unassigned#csv", "icon": "upload"},
                    {"name": "QR ZIP Oluştur", "url": "/admin/unassigned#qr", "icon": "folder-symlink"},
                ],
            }
        )

    return {"role": "admin" if is_admin else "user", "sections": sections}


@app.get("/api/stats/{shortid}")
def api_stats(shortid: str, days: int = 7):
    days = max(1, min(days, 90))
    with get_session() as session:
        tag = session.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag bulunamadı")
        start_date = datetime.utcnow().date() - timedelta(days=days - 1)
        rows = session.exec(
            select(func.date(Click.timestamp).label("d"), func.count(Click.id))
            .where(Click.tag_id == tag.id, Click.timestamp >= start_date)
            .group_by(func.date(Click.timestamp))
            .order_by(func.date(Click.timestamp))
        ).all()
    by_day = {row[0]: row[1] for row in rows}
    labels: List[str] = []
    values: List[int] = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        key = day.isoformat()
        labels.append(key)
        values.append(int(by_day.get(key, 0)))
    return JSONResponse({"labels": labels, "values": values, "shortid": shortid, "days": days})


@app.get("/stats/{shortid}", response_class=HTMLResponse)
def stats_page(request: Request, shortid: str, days: int = 7):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    with get_session() as session:
        tag = session.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag or tag.owner_user_id != user_id:
            raise HTTPException(status_code=403, detail="Yetkisiz erişim")
    days = max(1, min(days, 90))
    return render_template(
        request,
        "stats.html",
        {"shortid": shortid, "days": days},
    )
