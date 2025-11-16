from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

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
            "cover_url": "https://images.pexels.com/photos/7135016/pexels-photo-7135016.jpeg?auto=compress&cs=tinysrgb&w=800"
        },
        {
            "id": 2,
            "title": "Pixel Dreams",
            "artist": "Synthwave Kids",
            "album": "Neon City",
            "duration_sec": 205,
            "audio_url": "/static/audio/pixel_dreams.mp3",
            "cover_url": "https://images.pexels.com/photos/2387793/pexels-photo-2387793.jpeg?auto=compress&cs=tinysrgb&w=800"
        },
        {
            "id": 3,
            "title": "Rainy Window Study",
            "artist": "Chillhop Studio",
            "album": "Rain Tapes",
            "duration_sec": 194,
            "audio_url": "/static/audio/rainy_window.mp3",
            "cover_url": "https://images.pexels.com/photos/3742711/pexels-photo-3742711.jpeg?auto=compress&cs=tinysrgb&w=800"
        },
    ]


# Trang chính: player
@app.get("/")
def index():
    return FileResponse("index.html")


# 🔹 Trang Library
@app.get("/library")
def library():
    return FileResponse("library.htm")


# (tuỳ chọn) Trang About
@app.get("/about")
def about():
    return FileResponse("about.html")
