diff --git a/db.py b/db.py
index 3a6285d35ad0f4e1407b2a5cd2ef25b065d0b844..844f2753e6a35e0955f928f5a5adaf3bf83e768b 100644
--- a/db.py
+++ b/db.py
@@ -1,69 +1,114 @@
 # db.py
+import os
 from datetime import datetime
 from typing import Optional
+
 from sqlmodel import SQLModel, Field, create_engine, Session, select
 
+SITE_CODE = os.getenv("SITE_CODE", "site")
+SERVER_CODE = os.getenv("SERVER_CODE", "srv")
+
 DATABASE_URL = "sqlite:///./app.db"
 engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
 
 class User(SQLModel, table=True):
     id: Optional[int] = Field(default=None, primary_key=True)
     email: str = Field(index=True, unique=True)
     password_hash: str
     name: Optional[str] = None
     created_at: datetime = Field(default_factory=datetime.utcnow)
 
 class Tag(SQLModel, table=True):
     id: Optional[int] = Field(default=None, primary_key=True)
     shortid: str = Field(index=True, unique=True)
+    stable_id: Optional[str] = Field(default=None, index=True, unique=True)
+    site_code: str = Field(default_factory=lambda: SITE_CODE)
+    server_code: str = Field(default_factory=lambda: SERVER_CODE)
     owner_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
     status: str = Field(default="active")
     created_at: datetime = Field(default_factory=datetime.utcnow)
 
 class Profile(SQLModel, table=True):
     id: Optional[int] = Field(default=None, primary_key=True)
     tag_id: int = Field(foreign_key="tag.id")
-    title: Optional[str] = None
-    description: Optional[str] = None
-    link: Optional[str] = None
-    image_url: Optional[str] = None
-    # ✅ Yeni alanlar
-    phone: Optional[str] = None
-    public_email: Optional[str] = None
-    instagram: Optional[str] = None
+    first_name: Optional[str] = None
+    last_name: Optional[str] = None
     linkedin: Optional[str] = None
-    theme_color: Optional[str] = Field(default="#2563eb")  # hex renk
-
+    facebook: Optional[str] = None
+    instagram: Optional[str] = None
+    whatsapp: Optional[str] = None
+    iban: Optional[str] = None
+    avatar_url: Optional[str] = None
+    logo_url: Optional[str] = None
     updated_at: datetime = Field(default_factory=datetime.utcnow)
 
 class Click(SQLModel, table=True):
     id: Optional[int] = Field(default=None, primary_key=True)
     tag_id: int = Field(foreign_key="tag.id")
     timestamp: datetime = Field(default_factory=datetime.utcnow)
     ip: Optional[str] = None
     ua: Optional[str] = None
 
 def ensure_profile_columns():
-    # SQLite'da eksik kolonları ekle
     needed = {
-        "phone": "TEXT",
-        "public_email": "TEXT",
-        "instagram": "TEXT",
+        "first_name": "TEXT",
+        "last_name": "TEXT",
         "linkedin": "TEXT",
-        "theme_color": "TEXT",
+        "facebook": "TEXT",
+        "instagram": "TEXT",
+        "whatsapp": "TEXT",
+        "iban": "TEXT",
+        "avatar_url": "TEXT",
+        "logo_url": "TEXT",
     }
     with engine.connect() as conn:
         cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info('profile')").fetchall()}
         for col, typ in needed.items():
             if col not in cols:
                 conn.exec_driver_sql(f"ALTER TABLE profile ADD COLUMN {col} {typ};")
 
+
+def ensure_tag_columns():
+    needed = {
+        "stable_id": "TEXT",
+        "site_code": "TEXT",
+        "server_code": "TEXT",
+    }
+    with engine.connect() as conn:
+        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info('tag')").fetchall()}
+        for col, typ in needed.items():
+            if col not in cols:
+                conn.exec_driver_sql(f"ALTER TABLE tag ADD COLUMN {col} {typ};")
+
+
+def ensure_tag_stable_ids():
+    with Session(engine) as session:
+        tags = session.exec(select(Tag)).all()
+        changed = False
+        for tag in tags:
+            if not tag.site_code:
+                tag.site_code = SITE_CODE
+                changed = True
+            if not tag.server_code:
+                tag.server_code = SERVER_CODE
+                changed = True
+            expected = f"{tag.site_code}-{tag.server_code}-{tag.shortid}"
+            if tag.stable_id != expected:
+                tag.stable_id = expected
+                changed = True
+            session.add(tag)
+        if changed:
+            session.commit()
+
+
 def init_db():
     SQLModel.metadata.create_all(engine)
     ensure_profile_columns()
+    ensure_tag_columns()
+    ensure_tag_stable_ids()
 
 from sqlmodel import Session
 
 def get_session():
     # commit sonrası objeleri expire etme → template'te rahatça kullan
     return Session(engine, expire_on_commit=False)
