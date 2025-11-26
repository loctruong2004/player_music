from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from collections import Counter   
import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
import secrets
import re
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
# ==== IMPORT THÊM CHO AI MODEL ====
import tempfile
from typing import Dict, Optional

import librosa as lb
import soundfile as sf
import numpy as np
import matplotlib.cm as cm
from PIL import Image

import torch
import torch.nn.functional as F
from torchvision import models, transforms
# ==================================
import pyodbc

# ================== SQL SERVER CONFIG ==================
server = '192.168.0.103'  # IP máy chứa SQL Server
database = 'music'
username = 'loctruong'
password = '11012004'
port = '1433'

conn_str = (
    f"DRIVER={{SQL Server}};"
    f"SERVER={server},{port};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password}"
)


def get_sql_conn():
    return pyodbc.connect(conn_str)


app = FastAPI()

# ================== SESSION ==================
SECRET_KEY = secrets.token_hex(32)  # random mỗi lần run
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# ================== DB SQLITE (LOCAL USERS.DB, NẾU CẦN) ==================
DB_PATH = "users.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()

    # Bảng users (SQLite dự phòng, hiện tại auth đang dùng SQL Server)
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

    # Bảng tracks local (không dùng nếu đã dùng [music].[dbo].[tracks])
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            artist TEXT,
            genre TEXT,
            filepath TEXT NOT NULL,
            duration_sec INTEGER
        );
        """
    )

    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup():
    init_db()


def hash_password(password: str) -> str:
    # TODO: thay bằng SHA256/BCrypt nếu muốn
    return password


# ================== STATIC & API TRACKS ==================

MUSIC_DIR = r"C:\Users\Loc truong\deploy_music_classify\data_music"

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/db_music", StaticFiles(directory=MUSIC_DIR), name="db_music")


# ------ HELPER CHO audio_url / cover_url & CHECK FILE TỒN TẠI ------

def build_audio_url(audio_url_db: Optional[str]) -> str:
    """
    DB hiện đang lưu dạng: /db_music/XYZ.wav
    => chỉ cần chuẩn hóa dấu \ thành / rồi trả ra y nguyên.
    """
    if not audio_url_db:
        return ""
    return audio_url_db.replace("\\", "/")


def build_cover_url(cover_url_db: Optional[str]) -> str:
    url = (cover_url_db or "/static/default_cover.jpg").replace("\\", "/")
    return url


def file_exists_in_music(audio_url_db: Optional[str]) -> bool:
    """
    Map từ /db_music/ABC.wav -> C:\...\data_music\ABC.wav
    để check file .wav có tồn tại thật không.
    """
    if not audio_url_db:
        return False

    url = audio_url_db.replace("\\", "/")
    prefix = "/db_music/"
    if url.startswith(prefix):
        rel_path = url[len(prefix):]  # "JFm7YDVlqnI.wav"
    else:
        # nếu lỡ lưu kiểu "JFm7YDVlqnI.wav" hay "db_music/..."
        rel_path = url.lstrip("/\\")
        if rel_path.lower().startswith("db_music/"):
            rel_path = rel_path[len("db_music/"):]

    full_path = os.path.join(MUSIC_DIR, rel_path)
    return os.path.exists(full_path)

# ================== YOUTUBE DOWNLOAD HELPER (yt-dlp) ==================

_SANITIZE = re.compile(r'[^a-zA-Z0-9_\-\.]+')

def _safe_name(s: str) -> str:
    return _SANITIZE.sub('_', s).strip('_')


def _yt_opts_common(out_dir: str, use_cookies: bool = False):
    """
    Common options cho yt-dlp: tải bestaudio -> WAV.
    Nếu use_cookies=True sẽ cố gắng lấy cookies từ Chrome
    (chỉ dùng được khi server chạy trên máy có Chrome, đã đăng nhập YT).
    """
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 5,
        "concurrent_fragment_downloads": 4,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.youtube.com/",
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
        "prefer_ffmpeg": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "forceipv4": True,
    }

    if use_cookies:
        # cố gắng lấy cookies từ Chrome local (nếu có)
        opts["cookiesfrombrowser"] = ("chrome",)

    return opts


def download_youtube_audio(url: str, out_dir: str) -> str:
    """
    Tải bestaudio từ YouTube -> WAV.
    Thử 2 lần:
      1) Không dùng cookies
      2) Nếu lỗi 403/forbidden -> thử lại với cookiesfrombrowser
    Trả về đường dẫn file .wav cuối cùng.
    """
    os.makedirs(out_dir, exist_ok=True)

    def _try_download(use_cookies: bool) -> str:
        ydl_opts = _yt_opts_common(out_dir, use_cookies=use_cookies)
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "audio")
            wav_guess = _safe_name(title) + ".wav"
            candidate = os.path.join(out_dir, wav_guess)
            if os.path.exists(candidate):
                return candidate

            # fallback: lấy file .wav mới nhất trong thư mục
            wavs = [
                os.path.join(out_dir, f)
                for f in os.listdir(out_dir)
                if f.lower().endswith(".wav")
            ]
            if not wavs:
                raise RuntimeError(
                    "Không tìm thấy file WAV sau khi tải. Kiểm tra ffmpeg/yt-dlp."
                )
            return max(wavs, key=os.path.getmtime)

    try:
        # lần 1: không dùng cookies
        return _try_download(use_cookies=False)
    except DownloadError as e:
        msg = str(e).lower()
        if "403" in msg or "forbidden" in msg:
            # lần 2: thử dùng cookies
            try:
                return _try_download(use_cookies=True)
            except Exception as e2:
                raise RuntimeError(
                    f"YT 403. Thử lại với cookiesfrombrowser thất bại: {e2}"
                ) from e
        raise

@app.get("/api/tracks")
def get_tracks():
    """
    Lấy danh sách bài hát từ [music].[dbo].[tracks]
    Chỉ trả những bài có file tồn tại trong thư mục MUSIC_DIR.
    """
    conn = get_sql_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT TOP (1000)
                id,
                title,
                artist,
                genre,
                album_id,
                audio_url,
                cover_url,
                duration_sec
            FROM [music].[dbo].[tracks]
            ORDER BY id
            """
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    result = []

    for row in rows:
        (
            track_id,
            title,
            artist,
            genre,
            album_id,
            audio_url_db,
            cover_url_db,
            duration_sec,
        ) = row

        # Bỏ các track mà file không tồn tại để tránh 404
        if not file_exists_in_music(audio_url_db):
            print(f"[WARN] Track id={track_id} audio_url={audio_url_db} không tìm thấy file trên ổ cứng, skip.")
            continue

        title = title or "Untitled"
        artist = artist or "Unknown"
        genre = genre or "Unknown"
        duration = duration_sec if duration_sec is not None else 0

        album = genre  # tạm dùng genre làm album

        audio_url = build_audio_url(audio_url_db)
        cover_url = build_cover_url(cover_url_db)

        result.append(
            {
                "id": track_id,
                "title": title,
                "artist": artist,
                "album": album,
                "genre": genre,
                "duration_sec": duration,
                "audio_url": audio_url,
                "cover_url": cover_url,
            }
        )

    return result


# ================== ROUTES HTML ==================


@app.get("/")
async def index(request: Request):
    if not request.session.get("user_id"):
        return FileResponse("auth.html")
    return FileResponse("index.html")


@app.get("/auth")
async def auth_page(request: Request):
    return FileResponse("auth.html")


@app.get("/library")
async def library(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/auth", status_code=302)
    return FileResponse("library.htm")


@app.get("/ai")
async def ai_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/auth", status_code=302)
    return FileResponse("test.html")


@app.get("/about")
async def about():
    return FileResponse("about.html")


# ================== PLAYLIST / PLAYER API ==================


@app.get("/api/my-playlist")
async def get_my_playlist(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_sql_conn()
    cursor = conn.cursor()
    try:
        # 1. Lấy playlist cho user (ưu tiên playlist default)
        cursor.execute(
            """
            SELECT TOP 1 id, name
            FROM [music].[dbo].[playlists]
            WHERE owner_user_id = ?
            ORDER BY 
                CASE WHEN is_default = 1 THEN 0 ELSE 1 END,
                created_at
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return []  # chưa có playlist nào

        playlist_id, playlist_name = row

        # 2. Lấy các bài trong playlist
        cursor.execute(
            """
            SELECT
                t.id,
                t.title,
                t.artist,
                t.genre,
                t.duration_sec,
                t.audio_url,
                t.cover_url
            FROM [music].[dbo].[playlist_tracks] pt
            JOIN [music].[dbo].[tracks] t
                ON t.id = pt.track_id
            WHERE pt.playlist_id = ?
            ORDER BY pt.sort_order, pt.added_at
            """,
            (playlist_id,),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    result = []
    for (
        track_id,
        title,
        artist,
        genre,
        duration_sec,
        audio_url_db,
        cover_url_db,
    ) in rows:

        # Bỏ track nếu file audio bị mất để khỏi bị 404 ở frontend
        if not file_exists_in_music(audio_url_db):
            print(f"[WARN] Playlist track id={track_id} audio_url={audio_url_db} không có file, skip.")
            continue

        title = title or "Untitled"
        artist = artist or "Unknown"
        genre = genre or "Unknown"
        duration = duration_sec if duration_sec is not None else 0

        audio_url = build_audio_url(audio_url_db)
        cover_url = build_cover_url(cover_url_db)

        result.append(
            {
                "id": track_id,
                "title": title,
                "artist": artist,
                "album": genre,
                "genre": genre,
                "duration_sec": duration,
                "audio_url": audio_url,
                "cover_url": cover_url,
                "playlist_name": playlist_name,
            }
        )

    return result


@app.post("/api/player/play")
def api_play_track(
    request: Request,
    track_id: int = Body(..., embed=True),  # JSON: { "track_id": 6 }
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")

    # Có thể lưu vào session để index.html đọc lại
    request.session["current_track_id"] = track_id

    print(f"[PLAYER] user_id={user_id} play track_id={track_id}")
    return {"ok": True, "track_id": track_id}

from pydantic import BaseModel
from typing import Optional

class AddTrackPayload(BaseModel):
    track_id: int
    position: Optional[str] = None  # "top" hoặc None/bottom
@app.post("/api/playlists/add-track")
def api_add_track_to_default_playlist(
    request: Request,
    payload: AddTrackPayload,   # nhận JSON: { "track_id": ..., "position": "top" | ... }
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")

    track_id = payload.track_id
    position = (payload.position or "").lower().strip()  # "top" hoặc ""

    conn = get_sql_conn()
    cur = conn.cursor()
    try:
        # 1. Lấy playlist default của user
        cur.execute(
            """
            SELECT id
            FROM [music].[dbo].[playlists]
            WHERE owner_user_id = ? AND is_default = 1
            """,
            (user_id,),
        )
        row = cur.fetchone()

        if not row:
            # 2. Nếu chưa có, tạo playlist default
            cur.execute(
                """
                INSERT INTO [music].[dbo].[playlists]
                    (name, description, owner_user_id, is_default, is_public, created_at, updated_at)
                VALUES (?, ?, ?, 1, 1, SYSDATETIME(), SYSDATETIME())
                """,
                ("My Favorites", "Default playlist", user_id),
            )
            cur.execute("SELECT SCOPE_IDENTITY()")
            playlist_id = int(cur.fetchone()[0])
        else:
            playlist_id = int(row[0])

        # ================== CASE position == "top" ==================
        if position == "top":
            # 3A. Kiểm tra track đã tồn tại trong playlist chưa
            cur.execute(
                """
                SELECT sort_order
                FROM [music].[dbo].[playlist_tracks]
                WHERE playlist_id = ? AND track_id = ?
                """,
                (playlist_id, track_id),
            )
            row_exist = cur.fetchone()

            # Lấy sort_order nhỏ nhất hiện có để chèn lên đầu
            cur.execute(
                """
                SELECT ISNULL(MIN(sort_order), 0)
                FROM [music].[dbo].[playlist_tracks]
                WHERE playlist_id = ?
                """,
                (playlist_id,),
            )
            min_order_val = cur.fetchone()[0]
            # Nếu chưa có bài nào thì sẽ là 0 => mình cho bài đầu là 1
            if min_order_val == 0:
                new_order = 1
            else:
                # Đẩy lên trước tất cả bằng cách lấy nhỏ hơn nhỏ nhất
                new_order = min_order_val - 1

            if row_exist:
                # Đã có -> chỉ update sort_order để đẩy lên đầu
                cur.execute(
                    """
                    UPDATE [music].[dbo].[playlist_tracks]
                    SET sort_order = ?, added_at = SYSDATETIME()
                    WHERE playlist_id = ? AND track_id = ?
                    """,
                    (new_order, playlist_id, track_id),
                )
                conn.commit()
                print(
                    f"[PLAYLIST] user_id={user_id} move track_id={track_id} to TOP of playlist_id={playlist_id}"
                )
                return {
                    "ok": True,
                    "playlist_id": playlist_id,
                    "duplicated": True,
                    "moved_to_top": True,
                    "position": "top",
                }
            else:
                # Chưa có -> chèn mới ở đầu
                cur.execute(
                    """
                    INSERT INTO [music].[dbo].[playlist_tracks]
                        (playlist_id, track_id, sort_order, added_at)
                    VALUES (?, ?, ?, SYSDATETIME())
                    """,
                    (playlist_id, track_id, new_order),
                )
                conn.commit()
                print(
                    f"[PLAYLIST] user_id={user_id} INSERT track_id={track_id} at TOP playlist_id={playlist_id}"
                )
                return {
                    "ok": True,
                    "playlist_id": playlist_id,
                    "duplicated": False,
                    "moved_to_top": False,
                    "position": "top",
                }

        # ================== CASE bình thường (thêm xuống cuối) ==================
        # 3B. Không cho trùng: nếu đã có thì thôi
        cur.execute(
            """
            SELECT COUNT(*)
            FROM [music].[dbo].[playlist_tracks]
            WHERE playlist_id = ? AND track_id = ?
            """,
            (playlist_id, track_id),
        )
        (cnt_exist,) = cur.fetchone()
        if cnt_exist > 0:
            print(
                f"[PLAYLIST] track_id={track_id} đã tồn tại trong playlist_id={playlist_id}"
            )
            return {
                "ok": True,
                "playlist_id": playlist_id,
                "duplicated": True,
                "position": "bottom",
            }

        # 4. Tìm sort_order lớn nhất hiện tại (để thêm xuống cuối)
        cur.execute(
            """
            SELECT ISNULL(MAX(sort_order), 0)
            FROM [music].[dbo].[playlist_tracks]
            WHERE playlist_id = ?
            """,
            (playlist_id,),
        )
        max_order = cur.fetchone()[0] or 0

        # 5. Thêm bài vào cuối
        cur.execute(
            """
            INSERT INTO [music].[dbo].[playlist_tracks]
                (playlist_id, track_id, sort_order, added_at)
            VALUES (?, ?, ?, SYSDATETIME())
            """,
            (playlist_id, track_id, max_order + 1),
        )

        conn.commit()
        print(
            f"[PLAYLIST] user_id={user_id} add track_id={track_id} to END of playlist_id={playlist_id}"
        )
        return {
            "ok": True,
            "playlist_id": playlist_id,
            "duplicated": False,
            "position": "bottom",
        }

    finally:
        cur.close()
        conn.close()


@app.post("/api/playlists/remove-track")
def api_remove_track_from_default_playlist(
    request: Request,
    track_id: int = Body(..., embed=True),  # JSON: { "track_id": 4 }
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")

    conn = get_sql_conn()
    cur = conn.cursor()
    try:
        # 1. Lấy playlist default của user
        cur.execute(
            """
            SELECT id
            FROM [music].[dbo].[playlists]
            WHERE owner_user_id = ? AND is_default = 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            # Không có playlist default để xóa
            return {"ok": False, "reason": "no_default_playlist"}

        playlist_id = int(row[0])

        # 2. Xóa track khỏi playlist_tracks
        cur.execute(
            """
            DELETE FROM [music].[dbo].[playlist_tracks]
            WHERE playlist_id = ? AND track_id = ?
            """,
            (playlist_id, track_id),
        )
        deleted_rows = cur.rowcount
        conn.commit()

        print(
            f"[PLAYLIST] user_id={user_id} remove track_id={track_id} from playlist_id={playlist_id}, deleted_rows={deleted_rows}"
        )

        return {"ok": True, "deleted": deleted_rows}

    finally:
        cur.close()
        conn.close()


# ================== AUTH BACKEND ==================
# ================== AUTH BACKEND (NO HASH) ==================

from fastapi import Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime

@app.post("/auth/register")
async def register(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    # 1. Check confirm mật khẩu
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Mật khẩu nhập lại không khớp")

    pw_to_store = password  # lưu plain text

    conn = get_sql_conn()
    cursor = conn.cursor()
    try:
        # 2. Check email đã tồn tại chưa
        cursor.execute(
            "SELECT COUNT(*) FROM [music].[dbo].[users] WHERE email = ?",
            (email,),
        )
        (count_existing,) = cursor.fetchone()
        if count_existing > 0:
            raise HTTPException(status_code=400, detail="Email đã được đăng ký")

        # 3. (tuỳ chọn) check trùng username
        cursor.execute(
            "SELECT COUNT(*) FROM [music].[dbo].[users] WHERE username = ?",
            (username,),
        )
        (count_username,) = cursor.fetchone()
        if count_username > 0:
            raise HTTPException(status_code=400, detail="Username đã được sử dụng")

        # 4. INSERT user mới
        cursor.execute(
            """
            INSERT INTO [music].[dbo].[users]
                (name, username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, username, email, pw_to_store, datetime.utcnow()),
        )

        # 5. Lấy lại user vừa insert (dựa theo email)
        cursor.execute(
            """
            SELECT TOP (1) id, name
            FROM [music].[dbo].[users]
            WHERE email = ?
            ORDER BY id DESC
            """,
            (email,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=500,
                detail="Không lấy được thông tin user sau khi đăng ký",
            )

        user_id, user_name = row

        # 6. Tạo luôn playlist default cho user này
        cursor.execute(
            """
            INSERT INTO [music].[dbo].[playlists]
                (name, description, owner_user_id, is_default, is_public, created_at, updated_at)
            VALUES (?, ?, ?, 1, 1, SYSDATETIME(), SYSDATETIME())
            """,
            ("My Favorites", "Default playlist", user_id),
        )

        # 7. Commit tất cả
        conn.commit()

    finally:
        cursor.close()
        conn.close()

    # 8. Set session + redirect về trang chủ
    request.session["user_id"] = int(user_id)
    request.session["user_name"] = user_name   # lấy từ DB luôn
    request.session["user_email"] = email

    return RedirectResponse(url="/", status_code=303)



@app.post("/auth/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    pw_plain = password  # mật khẩu user gõ vào

    conn = get_sql_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, name, email, password_hash
            FROM [music].[dbo].[users]
            WHERE email = ?
            """,
            (email,),
        )
        row = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    # Không tìm thấy email
    if not row:
        return RedirectResponse(url="/auth?error=invalid_email", status_code=303)

    user_id, name, email_db, password_hash_db = row

    # Chuẩn hoá mật khẩu trong DB
    if password_hash_db is None:
        password_hash_db = ""
    else:
        password_hash_db = str(password_hash_db).strip()

    # So sánh trực tiếp plaintext
    if password_hash_db != pw_plain:
        return RedirectResponse(url="/auth?error=wrong_password", status_code=303)

    # Login OK -> set session
    request.session["user_id"] = int(user_id)
    request.session["user_name"] = name
    request.session["user_email"] = email_db

    return RedirectResponse(url="/", status_code=303)


@app.get("/api/me")
async def get_me(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse({"authenticated": False}, status_code=401)

    return {
        "authenticated": True,
        "id": user_id,
        "name": request.session.get("user_name"),
        "email": request.session.get("user_email"),
    }


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth", status_code=303)

# ================== AI GENRE CLASSIFICATION API ==================

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_model_cache: Dict[str, tuple] = {}


def load_ai_model(model_name: str):
    if model_name == "Model 5 class: bolero, cailuong, cheo, danca, nhacdo":
        classes = ["bolero", "cailuong", "cheo", "danca", "nhacdo"]
        model_path = "./efficientnet_b0_5_lager.pth"
        num_classes = 5

    elif model_name == "Model 7 class: bolero, cai luong, cheo, dan ca, nhac do, thieu nhi,other":
        classes = [
            "bolero",
            "cailuong",
            "cheo",
            "danca",
            "nhacdo",
            "other",
            "thieunhi",
        ]
        model_path = "./efficientnet_b0_7_final.pth"
        num_classes = 7

    elif model_name == "Model 8 class: 'Pop', 'bolero', 'cailuong', 'chauvan', 'cheo', 'danca', 'rap', 'remix'":
        classes = [
            "Pop",
            "bolero",
            "cailuong",
            "chauvan",
            "cheo",
            "danca",
            "rap",
            "remix",
        ]
        model_path = "./train_with_8_class.pth"
        num_classes = 8

    else:
        raise HTTPException(status_code=400, detail=f"Model không hợp lệ: {model_name}")

    if model_name in _model_cache:
        return _model_cache[model_name]

    try:
        model = models.efficientnet_b0(weights=None)
    except TypeError:
        model = models.efficientnet_b0(pretrained=False)

    model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, num_classes)

    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    _model_cache[model_name] = (model, classes)
    return model, classes


ai_transform = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]
)


def get_fft(samples, n_fft=2048, hop_length=512):
    for index, item in samples.items():
        D = np.abs(lb.stft(item["sampling"], n_fft=n_fft, hop_length=hop_length))
        samples[index]["stft"] = D
    return samples


def get_mel_spectrogram(samples, sr=22050):
    for index, item in samples.items():
        S = lb.feature.melspectrogram(y=item["sampling"], sr=sr)
        S_db = lb.amplitude_to_db(S, ref=np.max)
        samples[index]["mel-spec-db"] = S_db
    return samples


def save_mel_spec(samples, root):
    os.makedirs(root, exist_ok=True)
    image_paths = []

    for index, item in samples.items():
        S_db = item["mel-spec-db"]

        file_name = os.path.splitext(os.path.basename(item["dir"]))[0]
        out_path = os.path.join(root, file_name + ".png")

        S_db_norm = (S_db - S_db.min()) / (S_db.max() - S_db.min())
        S_rgb = cm.viridis(S_db_norm)[:, :, :3]
        S_rgb = (S_rgb * 255).astype(np.uint8)

        im = Image.fromarray(S_rgb).resize((224, 224))
        im.save(out_path)

        image_paths.append(out_path)

    return image_paths

@app.post("/api/classify")
async def classify_alias(
    model_name: str = Form(...),
    file: Optional[UploadFile] = File(None),
    youtube_url: Optional[str] = Form(None),
):
    """
    Alias cho /api/ai/predict, dùng cùng logic (file hoặc youtube_url).
    """
    return await ai_predict(
        model_name=model_name,
        file=file,
        youtube_url=youtube_url,
    )


@app.post("/api/ai/predict")
async def ai_predict(
    model_name: str = Form(...),
    file: Optional[UploadFile] = File(None),
    youtube_url: Optional[str] = Form(None),
):
    """
    - Nếu có youtube_url -> tải audio bằng yt-dlp -> phân loại.
    - Nếu không có youtube_url -> dùng file upload như cũ.
    """
    if not file and not youtube_url:
        raise HTTPException(
            status_code=400,
            detail="Cần upload file hoặc cung cấp youtube_url",
        )

    try:
        # Dùng thư mục tạm cho cả 2 case
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1) Chuẩn bị đường dẫn audio
            if youtube_url:
                url = youtube_url.strip()
                if not url:
                    raise HTTPException(status_code=400, detail="YouTube URL trống.")
                try:
                    audio_path = download_youtube_audio(url, tmpdir)
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Không tải được audio từ YouTube: {e}",
                    )
            else:
                # file upload
                if not file:
                    raise HTTPException(
                        status_code=400,
                        detail="Không có file upload.",
                    )
                suffix = os.path.splitext(file.filename)[1]
                if not suffix:
                    suffix = ".audio"
                audio_path = os.path.join(tmpdir, "uploaded" + suffix)
                with open(audio_path, "wb") as f:
                    f.write(await file.read())

            # 2) Load model
            model, class_names = load_ai_model(model_name)

            results = []
            segment_stats = []  # lưu kết quả từng đoạn cho frontend

            # 3) Load audio (librosa)
            y, sr = lb.load(audio_path, sr=None)
            duration = 30  # 30s/segment
            segment_samples = duration * sr
            total_samples = len(y)
            num_segments = total_samples // segment_samples

            if num_segments == 0:
                return {
                    "result": "⚠️ File quá ngắn (< 30s). Không thể xử lý.",
                    "segments": [],
                    "top_labels": [],
                }

            base_filename = os.path.splitext(os.path.basename(audio_path))[0]
            output_folder = os.path.join(tmpdir, "predict")
            os.makedirs(output_folder, exist_ok=True)

            # 4) Cắt audio thành từng đoạn 30s và lưu tạm
            samples = {}
            for i in range(num_segments):
                start = i * segment_samples
                end = start + segment_samples
                segment = y[start:end]

                new_filename = f"{base_filename}_part{i+1}.wav"
                new_path = os.path.join(output_folder, new_filename)

                sf.write(new_path, segment, sr)
                samples[i] = {"dir": new_path, "sampling": segment}

            # 5) Tạo Mel-spectrogram -> ảnh
            samples = get_fft(samples)
            samples = get_mel_spectrogram(samples, sr)
            mel_root = os.path.join(output_folder, "mel-images")
            list_test = save_mel_spec(samples, mel_root)

            # 6) Chạy model trên từng ảnh mel
            for idx, path in enumerate(list_test):
                image_pil = Image.open(path).convert("RGB")
                image_pil = image_pil.resize((224, 224))
                image_tensor = ai_transform(image_pil).unsqueeze(0).to(device)

                with torch.no_grad():
                    outputs = model(image_tensor)
                    probs = F.softmax(outputs, dim=1)
                    conf, pred = torch.max(probs, 1)

                output_class = class_names[pred.item()]
                percentage = conf.item() * 100

                start_time = str(timedelta(seconds=idx * duration))
                end_time = str(timedelta(seconds=(idx + 1) * duration))

                # Chuỗi hiển thị cho từng đoạn
                results.append(
                    f"[{start_time} → {end_time}] → {output_class} ({percentage:.2f}%)"
                )

                segment_stats.append(
                    {
                        "start": start_time,
                        "end": end_time,
                        "label": output_class,
                        "confidence": round(percentage, 2),
                    }
                )

            # 7) Tính top 2 thể loại xuất hiện nhiều nhất
            label_counts = Counter(s["label"] for s in segment_stats)
            top_labels = [label for label, _ in label_counts.most_common(2)]

            # Thư mục tmpdir sẽ tự xóa khi ra khỏi with -> không cần os.remove()
            return {
                "result": "\n".join(results),
                "segments": segment_stats,
                "top_labels": top_labels,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
