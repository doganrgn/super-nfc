# db.py
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, create_engine, Session

DATABASE_URL = "sqlite:///./app.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# ---------------------
# Modeller
# ---------------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)  # üretimde UNIQUE index önerilir
    password_hash: str
    name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Tag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shortid: str = Field(index=True)  # üretimde UNIQUE index önerilir
    owner_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Profile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tag_id: int = Field(foreign_key="tag.id")

    # Kartvizit / profil alanları
    full_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    image_url: Optional[str] = None

    phone: Optional[str] = None
    public_email: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None
    facebook: Optional[str] = None
    whatsapp: Optional[str] = None
    iban: Optional[str] = None

    theme_color: Optional[str] = Field(default="#2563eb")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Click(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tag_id: int = Field(foreign_key="tag.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip: Optional[str] = None
    ua: Optional[str] = None

# ---------------------
# Basit migrasyon: eksik kolonları ekle
# ---------------------
def ensure_profile_columns():
    needed = {
        "full_name": "TEXT",
        "phone": "TEXT",
        "public_email": "TEXT",
        "instagram": "TEXT",
        "linkedin": "TEXT",
        "facebook": "TEXT",
        "whatsapp": "TEXT",
        "iban": "TEXT",
        "theme_color": "TEXT",
        "updated_at": "DATETIME",
    }
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info('profile')").fetchall()}
        for col, typ in needed.items():
            if col not in cols:
                conn.exec_driver_sql(f"ALTER TABLE profile ADD COLUMN {col} {typ};")

# ---------------------
# DB init & session
# ---------------------
def init_db():
    SQLModel.metadata.create_all(engine)
    ensure_profile_columns()

def get_session() -> Session:
    # expire_on_commit=False -> render sırasında DetachedInstanceError riskini azaltır
    return Session(engine, expire_on_commit=False)
