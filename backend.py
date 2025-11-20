from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

import sqlite3
import hashlib
import os
from datetime import datetime

app = FastAPI()

# ================== SESSION ==================
# secret_key phải là chuỗi random, bạn đổi lại cho an toàn
app.add_middleware(SessionMiddleware, secret_key="change_this_to_a_long_random_secret")


# ================== DB USER (SQLite đơn giản) ==================
DB_PATH = "users.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            username TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            created_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup():
    init_db()


def hash_password(password: str) -> str:
    # Demo: dùng sha256 cho đơn giản (sản phẩm thật nên dùng bcrypt / passlib)
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ================== STATIC & API TRACKS ==================
# phục vụ thư mục static (audio, hình...)
app.mount("/static", StaticFiles(directory="static"), name="static")


# API trả danh sách bài hát
@app.get("/api/tracks")
def get_tracks():
    return [
        {
            "id": 1,
            "title": "Midnight Coding Session",
            "artist": "LTX Lo-fi",
            "album": "Night Drive",
            "duration_sec": 182,
            "audio_url": "/static/audio/midnight_coding.mp3",
            "cover_url": "https://images.pexels.com/photos/7135016/pexels-photo-7135016.jpeg?auto=compress&cs=tinysrgb&w=800",
        },
        {
            "id": 2,
            "title": "Pixel Dreams",
            "artist": "Synthwave Kids",
            "album": "Neon City",
            "duration_sec": 205,
            "audio_url": "/static/audio/pixel_dreams.mp3",
            "cover_url": "https://images.pexels.com/photos/2387793/pexels-photo-2387793.jpeg?auto=compress&cs=tinysrgb&w=800",
        },
        {
            "id": 3,
            "title": "Rainy Window Study",
            "artist": "Chillhop Studio",
            "album": "Rain Tapes",
            "duration_sec": 194,
            "audio_url": "/static/audio/rainy_window.mp3",
            "cover_url": "https://images.pexels.com/photos/3742711/pexels-photo-3742711.jpeg?auto=compress&cs=tinysrgb&w=800",
        },
    ]


# ================== ROUTES HTML ==================

# 🔹 Trang nghe nhạc (player) – YÊU CẦU ĐĂNG NHẬP
@app.get("/")
async def index(request: Request):
    if not request.session.get("user_id"):
        # chưa login -> về /auth (trang login/register)
        return RedirectResponse(url="/auth", status_code=302)
    # đã login -> trả index.html (trang player)
    return FileResponse("index.html")


# 🔹 Trang auth (login / register UI)
@app.get("/auth")
async def auth_page(request: Request):
    if request.session.get("user_id"):
        # đã login rồi mà vẫn vào /auth -> đá về player
        return RedirectResponse(url="/", status_code=302)
    return FileResponse("auth.html")


# 🔹 Trang Library (có thể cũng yêu cầu login)
@app.get("/library")
async def library(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/auth", status_code=302)
    return FileResponse("library.htm")


# 🔹 Trang About
@app.get("/about")
async def about():
    return FileResponse("about.html")


# ================== AUTH BACKEND ==================

# ĐĂNG KÝ
@app.post("/auth/register")
async def register(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    if password != confirm_password:
        # Có thể sau này bạn trả JSON để frontend show error
        raise HTTPException(status_code=400, detail="Mật khẩu nhập lại không khớp")

    pw_hash = hash_password(password)

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO users (name, username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, username, email, pw_hash, datetime.utcnow().isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Email đã được đăng ký")
    conn.close()

    # Lưu session -> coi như đã login
    conn = get_conn()
    cur = conn.execute("SELECT id, name FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()

    request.session["user_id"] = row["id"]
    request.session["user_name"] = row["name"]
    request.session["user_email"] = email

    # Redirect thẳng vào trang nghe nhạc
    return RedirectResponse(url="/", status_code=303)

# ĐĂNG NHẬP (bypass, đăng nhập bừa cũng vào được)
@app.post("/auth/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    # BỎ QUA kiểm tra DB, mật khẩu, hash, v.v.
    # Gán thẳng session cho user "Dev User" với email nhập vào

    request.session["user_id"] = -1          # id giả
    request.session["user_name"] = "Dev User"
    request.session["user_email"] = email

    # Redirect vào player
    return RedirectResponse(url="/", status_code=303)


# ĐĂNG XUẤT
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth", status_code=303)
