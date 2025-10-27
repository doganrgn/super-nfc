import json, os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import secrets
import csv
from io import StringIO
from fastapi import Response

from fastapi.responses import StreamingResponse
import io, zipfile

import qrcode
from qrcode.image.pil import PilImage


from sqlalchemy.sql import func
from fastapi.responses import JSONResponse


from db import init_db, get_session, User, Tag, Profile, Click

from sqlmodel import select
from auth import hash_password, verify_password, set_session_cookie, clear_session_cookie, get_current_user_id

PUBLIC_BASE_URL = "http://192.168.1.188:8000"   # örn: "https://example.com" ya da "http://192.168.1.188:8000"
PURCHASE_URL = "https://satin-al.example.com"   # ürün satın alma (şimdilik placeholder)
SUPPORT_EMAIL = "destek@example.com"            # destek e-posta adresin

...

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI()
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ADMIN_EMAILS = {"doganrgn@gmail.com"}  # ← şimdilik burada sabit tutuyoruz

def get_current_user(request: Request):
    uid = get_current_user_id(request)
    if not uid:
        return None, None
    with get_session() as s:
        u = s.exec(select(User).where(User.id == uid)).first()
        return uid, (u.email if u else None)

def require_login(request: Request):
    uid = get_current_user_id(request)
    if not uid:
        # login’e at
        return RedirectResponse(url="/login", status_code=303)
    return None

def require_admin(request: Request):
    uid, email = get_current_user(request)
    if not uid:
        return RedirectResponse(url="/login", status_code=303)
    if email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")
    return None


@app.on_event("startup")
def on_startup():
    init_db()
    DEMO = False  # True ise yalnızca yerelde demo üretir
    if DEMO:
        with get_session() as s:
            if not s.exec(select(Tag).where(Tag.shortid == "deneme123")).first():
                t = Tag(shortid="deneme123")
                s.add(t); s.commit(); s.refresh(t)
                p = Profile(tag_id=t.id, title="Demo Başlık")
                s.add(p); s.commit()


@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user_id = get_current_user_id(request)
    return templates.TemplateResponse("home.html", {"request": request, "user_id": user_id})

# --- Auth ---

@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})

@app.post("/register")
def register_submit(email: str = Form(...), password: str = Form(...), name: Optional[str] = Form(None)):
    email = email.strip().lower()
    with get_session() as s:
        if s.exec(select(User).where(User.email == email)).first():
            return RedirectResponse(url="/login?e=exists", status_code=303)
        u = User(email=email, password_hash=hash_password(password), name=name)
        s.add(u)
        s.commit()
        s.refresh(u)
    resp = RedirectResponse(url="/dashboard", status_code=303)
    set_session_cookie(resp, u.id)
    return resp

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, e: Optional[str] = None):
    error = None
    if e == "exists":
        error = "Bu e-posta zaten kayıtlı. Lütfen giriş yapın."
    elif e == "invalid":
        error = "E-posta veya parola hatalı."
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
def login_submit(email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    with get_session() as s:
        u = s.exec(select(User).where(User.email == email)).first()
        if not u or not verify_password(password, u.password_hash):
            return RedirectResponse(url="/login?e=invalid", status_code=303)
        resp = RedirectResponse(url="/dashboard", status_code=303)
        set_session_cookie(resp, u.id)
        return resp

@app.post("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(resp)
    return resp


# --- dashboard: tag'ların tıklama sayısını getir ---
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    with get_session() as s:
        my_tags = s.exec(select(Tag).where(Tag.owner_user_id == user_id)).all()
        # her tag için click count al
        tags_with_counts = []
        for t in my_tags:
            count = len(s.exec(select(Click).where(Click.tag_id == t.id)).all())
            tags_with_counts.append({"shortid": t.shortid, "count": count})
    return templates.TemplateResponse("dashboard.html", {"request": request, "user_id": user_id, "tags": tags_with_counts})

from fastapi import Form  # en üstte importların arasında varsa tekrar ekleme
from fastapi import Response  # sende zaten var

from fastapi import Form

@app.post("/admin/generate")
def admin_generate(request: Request, n: int = Form(10)):
    # admin kontrol
    resp = require_admin(request)
    if resp:
        return resp

    created = []
    with get_session() as s:
        for _ in range(max(1, min(n, 1000))):
            sid = generate_shortid(8)
            while s.exec(select(Tag).where(Tag.shortid == sid)).first():
                sid = generate_shortid(8)
            t = Tag(shortid=sid)
            s.add(t)
            s.commit()
            s.refresh(t)
            created.append(sid)

    # CSV döndür
    from io import StringIO
    import csv
    si = StringIO()
    w = csv.writer(si)
    w.writerow(["shortid"])
    for x in created:
        w.writerow([x])
    output = si.getvalue()
    return Response(
        content=output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=generated_tags.csv"}
    )

@app.get("/admin/unassigned", response_class=HTMLResponse)
def admin_unassigned(request: Request):
    # admin kontrol
    resp = require_admin(request)
    if resp:
        return resp

    with get_session() as s:
        empty_tags = s.exec(select(Tag).where(Tag.owner_user_id.is_(None))).all()
    return templates.TemplateResponse(
        "admin_unassigned.html",
        {"request": request, "tags": empty_tags}
    )

from fastapi import Form
import csv, io

@app.post("/admin/inventory_import")
def admin_inventory_import(request: Request, csv_text: str = Form("")):
    resp = require_admin(request)
    if resp: return resp
    csv_text = (csv_text or "").strip()
    if not csv_text:
        raise HTTPException(status_code=400, detail="Boş CSV")

    # shortid başlıklı tek kolon veya virgüllü/alt alta kısa id listesi kabul edelim
    buf = io.StringIO(csv_text)
    rdr = csv.reader(buf)
    created, skipped = 0, 0
    with get_session() as s:
        for row in rdr:
            if not row: continue
            sid = row[0].strip()
            if not sid: continue
            # var mı kontrol
            if s.exec(select(Tag).where(Tag.shortid == sid)).first():
                skipped += 1
                continue
            s.add(Tag(shortid=sid))
            s.commit()
            created += 1
    return RedirectResponse(url=f"/admin/unassigned?import_ok={created}&skip={skipped}", status_code=303)


from fastapi import Form

@app.post("/admin/qrzip")
def admin_qr_zip(request: Request, ids: str = Form(""), size: int = Form(10), border: int = Form(4)):
    # admin kontrol
    resp = require_admin(request)
    if resp:
        return resp

    # id listesi (boşluk, virgül veya satır başına bir shortid)
    raw = ids.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="ID listesi boş.")
    shortids = []
    for tok in raw.replace(",", " ").split():
        tok = tok.strip()
        if tok:
            shortids.append(tok)

    # DB'de var olanları filtrele (hatalı ID'leri atla)
    valid_ids = []
    with get_session() as s:
        for sid in shortids:
            if s.exec(select(Tag).where(Tag.shortid == sid)).first():
                valid_ids.append(sid)

    if not valid_ids:
        raise HTTPException(status_code=400, detail="Geçerli ID bulunamadı.")

    # ZIP oluştur
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for sid in valid_ids:
            # URL hazırla
            if PUBLIC_BASE_URL:
                url = f"{PUBLIC_BASE_URL}/t/{sid}"
            else:
                url = f"/t/{sid}"  # relative (tarayıcıda açarsan çalışır)

            # QR üret
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_Q,
                box_size=max(1, min(int(size), 20)),
                border=max(1, min(int(border), 10)),
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            # PNG'yi buffer'a yaz ve ZIP'e ekle
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            zf.writestr(f"qr_{sid}.png", buf.read())

    mem.seek(0)
    return StreamingResponse(mem, media_type="application/zip",
                             headers={"Content-Disposition": 'attachment; filename="qr_bulk.zip"'})

@app.get("/claim-info/{shortid}", response_class=HTMLResponse)
def claim_info(request: Request, shortid: str):
    # Tag var mı kontrol edelim (yanlış URL’e güzel bir mesaj)
    with get_session() as s:
        tag = s.exec(select(Tag).where(Tag.shortid == shortid)).first()
    if not tag:
        return templates.TemplateResponse(
            "tag_404.html",
            {"request": request, "shortid": shortid, "purchase_url": PURCHASE_URL, "support_email": SUPPORT_EMAIL},
            status_code=404
        )

    user_id = get_current_user_id(request)
    return templates.TemplateResponse(
        "claim_info.html",
        {"request": request, "shortid": shortid, "logged_in": bool(user_id)}
    )


@app.get("/t/{shortid}", response_class=HTMLResponse)
def show_tag(request: Request, shortid: str):
    with get_session() as s:
        tag = s.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            # ÖZEL 404 ŞABLONU
            return templates.TemplateResponse(
                "tag_404.html",
                {"request": request, "shortid": shortid, "purchase_url": PURCHASE_URL, "support_email": SUPPORT_EMAIL},
                status_code=404
            )
        profile = s.exec(select(Profile).where(Profile.tag_id == tag.id)).first()

        # (Ziyaret kaydı aynen kalsın)
        try:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent")
            s.add(Click(tag_id=tag.id, ip=ip, ua=ua))
            s.commit()
        except Exception:
            pass

        # Şablona dict vermeyi tercih ediyorsan:
        p = None
        if profile:
            p = {
                "title": profile.title,
                "description": profile.description,
                "link": profile.link,
                "image_url": profile.image_url,
                "phone": profile.phone,
                "public_email": profile.public_email,
                "instagram": profile.instagram,
                "linkedin": profile.linkedin,
                "theme_color": profile.theme_color,
            }

    return templates.TemplateResponse("tag.html", {"request": request, "tag_id": shortid, "p": p})



# --- Tag Sahiplenme ---

@app.get("/claim/{shortid}", response_class=HTMLResponse)
def claim_form(request: Request, shortid: str):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("claim.html", {"request": request, "shortid": shortid, "error": None})

@app.post("/claim/{shortid}")
def claim_submit(request: Request, shortid: str):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    with get_session() as s:
        tag = s.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag yok")
        if tag.owner_user_id and tag.owner_user_id != user_id:
            return templates.TemplateResponse("claim.html", {"request": request, "shortid": shortid, "error": "Bu tag başka bir kullanıcıya atanmış."})
        tag.owner_user_id = user_id
        s.add(tag)
        # profil yoksa oluştur
        prof = s.exec(select(Profile).where(Profile.tag_id == tag.id)).first()
        if not prof:
            prof = Profile(tag_id=tag.id)
            s.add(prof)
        s.commit()
    return RedirectResponse(url=f"/edit/{shortid}", status_code=303)

# --- Tag Düzenleme (yalnızca sahibi) ---

@app.get("/edit/{shortid}", response_class=HTMLResponse)
def edit_form(request: Request, shortid: str):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    with get_session() as s:
        tag = s.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag yok")
        if tag.owner_user_id != user_id:
            raise HTTPException(status_code=403, detail="Bu tag size ait değil")
        profile = s.exec(select(Profile).where(Profile.tag_id == tag.id)).first()
    return templates.TemplateResponse("edit.html", {"request": request, "tag_id": shortid, "p": profile})

@app.post("/edit/{shortid}")
async def edit_submit(
    request: Request,
    shortid: str,
    title: str = Form(""),
    description: str = Form(""),
    link: str = Form(""),
    phone: str = Form(""),
    public_email: str = Form(""),
    instagram: str = Form(""),
    linkedin: str = Form(""),
    theme_color: str = Form("#2563eb"),
    image: UploadFile | None = File(None),
):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    with get_session() as s:
        tag = s.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag yok")
        if tag.owner_user_id != user_id:
            raise HTTPException(status_code=403, detail="Bu tag size ait değil")

        profile = s.exec(select(Profile).where(Profile.tag_id == tag.id)).first()
        if not profile:
            profile = Profile(tag_id=tag.id)
            s.add(profile)
            s.commit()
            s.refresh(profile)


        
        # Görsel
        if image and image.filename:
            ext = os.path.splitext(image.filename)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                ext = ".jpg"
            safe_name = f"{shortid}{ext}"
            dest = UPLOAD_DIR / safe_name
            with dest.open("wb") as f:
                f.write(await image.read())
            profile.image_url = f"/uploads/{safe_name}"
        # Instagram normalizasyonu
        ig = instagram.strip()
        if ig:
            if ig.startswith("@"):
                ig = ig[1:]
            if not ig.startswith("http"):
                ig = f"https://instagram.com/{ig}"
        profile.instagram = ig

        # LinkedIn normalizasyonu
        li = linkedin.strip()
        if li and not li.startswith("http"):
            # kullanıcı sadece /in/kullanici verdiyse veya kullanıcı adını verdiyse:
            if li.startswith("/in/"):
                li = f"https://www.linkedin.com{li}"
            else:
                li = f"https://www.linkedin.com/in/{li}"
        profile.linkedin = li

        # Telefon sadece trimle (ileri doğrulamayı sonraya bırakıyoruz)
        profile.phone = phone.strip()

        # E-posta trimle
        profile.public_email = public_email.strip()

        # Link alanı (genel)
        lnk = link.strip()
        if lnk and not lnk.startswith("http"):
            lnk = "https://" + lnk
        profile.link = lnk
        
        # Metin alanları
        profile.title = title.strip()
        profile.description = description.strip()
        profile.link = link.strip()

        profile.phone = phone.strip()
        profile.public_email = public_email.strip()
        profile.instagram = instagram.strip()
        profile.linkedin = linkedin.strip()

        # basit hex doğrulama
        tc = theme_color.strip()
        if tc.startswith("#") and (len(tc) in (4, 7)):
            profile.theme_color = tc

        s.add(profile)
        s.commit()

    return RedirectResponse(url=f"/t/{shortid}", status_code=303)

# helper: kısa, çakışmasız shortid üret
def generate_shortid(length: int = 6) -> str:
    # token_urlsafe benzeri, ama daha kısa temiz string
    s = secrets.token_urlsafe(length)
    # temizle (,-_, büyük küçük olabilir) ve kısalt
    return s.replace("-", "").replace("_", "")[:length]
    
    
@app.get("/api/stats/{shortid}")
def api_stats(shortid: str, days: int = 7):
    # days: 7 veya 30 gibi
    days = max(1, min(days, 90))  # güvenli sınır

    with get_session() as s:
        tag = s.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag bulunamadı")

        # Son N günün tarihlerini üret (bugün dahil)
        from datetime import datetime, timedelta
        today = datetime.utcnow().date()
        start_date = today - timedelta(days=days - 1)

        # Gün bazında sayım (SQLite için func.date)
        # NOT: SQLAlchemy + SQLite: Click.timestamp (UTC) -> YYYY-MM-DD string
        rows = s.exec(
            select(
                func.date(Click.timestamp).label("d"),
                func.count(Click.id)
            ).where(
                Click.tag_id == tag.id,
                Click.timestamp >= start_date
            ).group_by(
                func.date(Click.timestamp)
            ).order_by(
                func.date(Click.timestamp)
            )
        ).all()

        # rows -> dict { "YYYY-MM-DD": count }
        by_day = {r[0]: r[1] for r in rows}

        # eksik günleri 0 ile doldur
        labels, values = [], []
        for i in range(days):
            d = start_date + timedelta(days=i)
            ds = d.isoformat()
            labels.append(ds)
            values.append(int(by_day.get(ds, 0)))

    return JSONResponse({"labels": labels, "values": values, "shortid": shortid, "days": days})

@app.get("/stats/{shortid}", response_class=HTMLResponse)
def stats_page(request: Request, shortid: str, days: int = 7):
    # giriş şartı koymak istersen:
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    # yetkisiz görüntülemeyi engellemek istersen (sahiplik kontrolü):
    with get_session() as s:
        tag = s.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag bulunamadı")
        if tag.owner_user_id != user_id:
            raise HTTPException(status_code=403, detail="Bu tag size ait değil")

    # sayfa Chart.js ile /api/stats’dan veri çekecek
    days = max(1, min(days, 90))
    return templates.TemplateResponse(
        "stats.html",
        {"request": request, "shortid": shortid, "days": days}
    )

from fastapi.responses import StreamingResponse
import io
import qrcode
from qrcode.image.pil import PilImage

@app.get("/qr/{shortid}")
def qr_code(shortid: str, size: int = 10, border: int = 4):
    # shortid kontrolü
    with get_session() as s:
        tag = s.exec(select(Tag).where(Tag.shortid == shortid)).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag bulunamadı")

    # URL'i burada oluştur (modül seviyesinde DEĞİL!)
    if PUBLIC_BASE_URL:
        url = f"{PUBLIC_BASE_URL}/t/{shortid}"
    else:
        # relative URL – tarayıcıda çalışır; başka cihazda okutacaksan PUBLIC_BASE_URL kullan
        url = f"/t/{shortid}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=max(1, min(size, 20)),
        border=max(1, min(border, 10)),
    )
    qr.add_data(url)
    qr.make(fit=True)

    img: PilImage = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png",
                             headers={"Content-Disposition": f'inline; filename="qr_{shortid}.png"'})
@app.get("/api/options")
def get_user_options(request: Request):
    user_id = get_current_user_id(request)
    if not user_id:
        return {"role": "guest", "options": []}

    with get_session() as s:
        user = s.exec(select(User).where(User.id == user_id)).first()

    # Basit admin kontrolü
    is_admin = user.email in ADMIN_EMAILS

    if is_admin:
        options = [
            {"name": "Kullanıcı Yönetimi", "url": "/admin/users"},
            {"name": "Tag Envanteri & Atama", "url": "/admin/unassigned"},
            {"name": "İçerik Moderasyonu", "url": "/admin/content"},
            {"name": "İstatistik & Raporlar", "url": "/admin/reports"},
            {"name": "Sistem Ayarları", "url": "/admin/settings"},
            {"name": "Destek Talepleri", "url": "/admin/support"},
            {"name": "Çıkış", "url": "/logout"},
        ]
        return {"role": "admin", "options": options}

    else:
        options = [
            {"name": "NFC Tag’imi Yönet", "url": "/dashboard"},
            {"name": "Profil/Ürün Sayfasını Düzenle", "url": "/edit"},
            {"name": "Görüntülenme & Tıklama İstatistikleri", "url": "/stats"},
            {"name": "Yönlendirme & QR Ayarları", "url": "/qr"},
            {"name": "Dosya & Görsel Yükleme", "url": "/edit"},
            {"name": "Hesap Ayarları", "url": "/account"},
            {"name": "Çıkış", "url": "/logout"},
        ]
        return {"role": "user", "options": options}
