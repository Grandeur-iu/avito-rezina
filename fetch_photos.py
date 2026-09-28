# -*- coding: utf-8 -*-
"""fetch_photos.py — скачать фото комплектов из папок Google Диска (photo_folders.json)
и сохранить ужатые копии в photos/<№>/<№>-<k>.jpg. Оригиналы во временную папку.
Запуск через venv gregario (там google-auth); ужатие — через системный python (там Pillow):
  "D:/Проекты Claud/gregario/.venv/Scripts/python.exe" fetch_photos.py download
  python fetch_photos.py resize
"""
import sys, os, json, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(os.environ.get("TEMP", HERE), "rezina_raw")
OUT = os.path.join(HERE, "photos")
SA = r"D:\Проекты Claud\_secrets\google_sa.json"

def download():
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession
    s = AuthorizedSession(Credentials.from_service_account_file(SA, scopes=["https://www.googleapis.com/auth/drive.readonly"]))
    m = json.load(open(os.path.join(HERE, "photo_folders.json")))
    for num, fid in m.items():
        if not fid: continue
        d = os.path.join(RAW, num); os.makedirs(d, exist_ok=True)
        files = s.get("https://www.googleapis.com/drive/v3/files", params={"q": f"'{fid}' in parents and trashed=false", "fields": "files(id,name,size,createdTime)", "pageSize": 100}).json()["files"]
        seen = set(); k = 0
        for f in sorted(files, key=lambda x: x["name"]):
            r = s.get(f"https://www.googleapis.com/drive/v3/files/{f['id']}?alt=media")
            h = hashlib.md5(r.content).hexdigest()
            if h in seen: continue   # дубль по содержимому
            seen.add(h); k += 1
            open(os.path.join(d, f"{k:02d}_{f['name']}"), "wb").write(r.content)
        print(num, "скачано", k, "уникальных из", len(files), flush=True)

def resize():
    from PIL import Image, ImageOps
    import pillow_heif; pillow_heif.register_heif_opener()   # iPhone отдаёт HEIC под именем .jpeg
    for num in sorted(os.listdir(RAW), key=int):
        d = os.path.join(RAW, num); o = os.path.join(OUT, num); os.makedirs(o, exist_ok=True)
        n = 0
        for i, fn in enumerate(sorted(os.listdir(d)), 1):
            im = ImageOps.exif_transpose(Image.open(os.path.join(d, fn))).convert("RGB")
            im.thumbnail((1600, 1600))
            im.save(os.path.join(o, f"{num}-{i:02d}.jpg"), "JPEG", quality=85, optimize=True); n += 1
        print(num, n, "фото →", o, flush=True)

if __name__ == "__main__":
    {"download": download, "resize": resize}[sys.argv[1]]()
