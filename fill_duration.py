# fill_duration.py

import os
import pyodbc
import librosa  # đã dùng trong backend rồi nên ok

# Thông tin kết nối y như backend FastAPI
server = '192.168.0.103'
database = 'mussic'
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

def main():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Lấy những track chưa có duration (NULL hoặc 0)
    cursor.execute("""
        SELECT id, filepath
        FROM tracks
        WHERE duration_sec IS NULL OR duration_sec = 0
    """)

    rows = cursor.fetchall()
    print(f"Found {len(rows)} tracks need duration")

    for track_id, filepath in rows:
        if not filepath:
            print(f"[ID {track_id}] filepath rỗng, bỏ qua")
            continue

        if not os.path.exists(filepath):
            print(f"[ID {track_id}] File không tồn tại: {filepath}")
            continue

        try:
            # Cách 1: dùng librosa.get_duration trực tiếp từ path
            duration = librosa.get_duration(path=filepath)
            duration_sec = int(round(duration))

            print(f"[ID {track_id}] {os.path.basename(filepath)} -> {duration_sec} sec")

            cursor.execute(
                "UPDATE tracks SET duration_sec = ? WHERE id = ?",
                duration_sec,
                track_id
            )
        except Exception as e:
            print(f"[ID {track_id}] Lỗi đọc file {filepath}: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Done update duration_sec!")

if __name__ == "__main__":
    main()
