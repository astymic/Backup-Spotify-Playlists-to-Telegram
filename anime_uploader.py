#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anime_uploader.py
==================
Загружает папку Openings - Endings-OSTs в один Telegram Topic.

Структура:
    Openings - Endings-OSTs/
        Attack on Titan/
            01 - Guren no Yumiya.flac
            02 - Shinzou wo Sasageyo.m4a
        Naruto/
            01 - Blue Bird.mp3
        ...

Результат:
    Topic "Anime Openings"
        [Attack on Titan]  🎵 Guren no Yumiya.mp3
        [Attack on Titan]  🎵 Shinzou wo Sasageyo.mp3
        [Naruto]           🎵 Blue Bird.mp3
        ...

Для каждого файла:
    1. Конвертируется в MP3 (если не MP3) через ffmpeg
    2. Отправляется в топик с подписью = название папки
"""

import io
import json
import os
import re
import subprocess
import sys
import time
import shutil
import tempfile
from pathlib import Path

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import requests
except ImportError:
    print("Установите: pip install requests")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Конфиг
# ──────────────────────────────────────────────────────────────────────────────

CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print("[!] config.json не найден. Запустите telegram_uploader.py для создания.")
        sys.exit(1)
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if cfg.get("BOT_TOKEN", "") in ("", "ВАШ_ТОКЕН_БОТА"):
        print("[!] Заполните BOT_TOKEN в config.json")
        sys.exit(1)
    return cfg


# ──────────────────────────────────────────────────────────────────────────────
# Telegram
# ──────────────────────────────────────────────────────────────────────────────

class TelegramBot:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"
        me = self._api("getMe")
        print(f"  [+] Бот: @{me['username']}")

    def _api(self, method: str, data: dict = None, files=None, timeout=180) -> dict:
        resp = requests.post(f"{self.base}/{method}", data=data, files=files, timeout=timeout)
        result = resp.json()
        if not result.get("ok"):
            raise RuntimeError(f"TG API: {result.get('description', result)}")
        return result["result"]

    def create_topic(self, chat_id: int, name: str) -> int:
        res = self._api("createForumTopic", {
            "chat_id":    chat_id,
            "name":       name[:128],
            "icon_color": 16766590,   # жёлтый — для аниме 🌟
        })
        return res["message_thread_id"]

    def send_audio(self, chat_id: int, thread_id: int,
                   path: Path, title: str, performer: str, caption: str) -> bool:
        with open(path, "rb") as f:
            try:
                self._api("sendAudio", data={
                    "chat_id":           chat_id,
                    "message_thread_id": thread_id,
                    "title":             title[:64],
                    "performer":         performer[:64],
                    "caption":           caption[:1024],
                }, files={"audio": (path.name, f, "audio/mpeg")}, timeout=300)
                return True
            except Exception as e:
                print(f" ОШИБКА: {e}")
                return False


# ──────────────────────────────────────────────────────────────────────────────
# Конвертация
# ──────────────────────────────────────────────────────────────────────────────

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav",
              ".aac", ".wma", ".mp4", ".mkv", ".webm", ".avi"}

def convert_to_mp3(src: Path, out_dir: Path) -> Path | None:
    """Конвертирует файл в MP3 через ffmpeg. Возвращает путь к MP3."""
    stem   = re.sub(r'[\\/*?:"<>|]', "_", src.stem).strip()
    dst    = out_dir / f"{stem}.mp3"

    if src.suffix.lower() == ".mp3":
        # Уже MP3 — просто копируем (не перекодируем)
        shutil.copy2(src, dst)
        return dst

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vn",                      # убрать видео
        "-acodec", "libmp3lame",
        "-q:a", "2",               # ~190 kbps VBR
        str(dst)
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")[-200:]
        print(f"\n    [!] ffmpeg ошибка: {err}")
        return None
    return dst


# ──────────────────────────────────────────────────────────────────────────────
# Основная логика
# ──────────────────────────────────────────────────────────────────────────────

def collect_tracks(root: Path) -> list[tuple[str, Path]]:
    """
    Рекурсивно собирает все аудио-файлы из подпапок.
    Возвращает список (subfolder_name, file_path), отсортированный:
        - по имени подпапки
        - внутри папки по имени файла
    """
    tracks = []
    for subdir in sorted(root.iterdir()):
        if not subdir.is_dir():
            continue
        files = sorted(
            f for f in subdir.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_EXTS
        )
        for f in files:
            tracks.append((subdir.name, f))
    return tracks


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║        >>  Anime OST Uploader  <<                    ║
║    Openings/Endings/OSTs → один Topic в Telegram     ║
╚══════════════════════════════════════════════════════╝
""")

    cfg     = load_config()
    bot     = TelegramBot(cfg["BOT_TOKEN"])
    chat_id = cfg["CHAT_ID"]
    delay   = cfg.get("DELAY_SECONDS", 5)

    # Путь и название топика — из config.json
    anime_dir  = cfg.get("ANIME_DIR", "")
    topic_name = cfg.get("ANIME_TOPIC_NAME", "Anime Openings")

    if not anime_dir:
        print("  [-] Укажите ANIME_DIR в config.json")
        print('       Пример: "ANIME_DIR": "E:\\\\муза\\\\Openings - Endings-OSTs"')
        sys.exit(1)

    src_root = Path(anime_dir)
    if not src_root.exists():
        print(f"  [-] Папка не найдена: {src_root}")
        print(f"       Проверьте ANIME_DIR в config.json")
        sys.exit(1)

    print(f"  Папка:  {src_root}")
    print(f"  Topic:  {topic_name}")

    # ── Сбор файлов ──────────────────────────────────────────────────────────
    print("\n  Сканирую файлы...")
    tracks = collect_tracks(src_root)
    if not tracks:
        print("  [-] Аудио-файлы не найдены.")
        sys.exit(0)

    # Статистика
    subfolders = sorted(set(n for n, _ in tracks))
    print(f"  Найдено папок:  {len(subfolders)}")
    print(f"  Всего файлов:   {len(tracks)}")
    for sub in subfolders[:10]:
        cnt = sum(1 for n, _ in tracks if n == sub)
        print(f"    • {sub}  ({cnt} файлов)")
    if len(subfolders) > 10:
        print(f"    ... и ещё {len(subfolders) - 10}")

    print(f"\n  Topic:   '{topic_name}'")
    print(f"  Группа:  {chat_id}")
    input("\n  Нажмите Enter для начала... (Ctrl+C для отмены)")

    # ── Создаём топик ────────────────────────────────────────────────────────
    print(f"\n  Создаю топик '{topic_name}'...")
    thread_id = bot.create_topic(chat_id, topic_name)
    print(f"  [+] thread_id = {thread_id}")
    time.sleep(1)

    # ── Временная папка для MP3 ───────────────────────────────────────────────
    tmp_dir = Path(tempfile.mkdtemp(prefix="anime_mp3_"))
    print(f"  Временная папка для конвертации: {tmp_dir}\n")

    ok_count = fail_count = conv_fail = 0
    total = len(tracks)

    try:
        for i, (subfolder, src_file) in enumerate(tracks, 1):
            label = f"{subfolder}  /  {src_file.name}"
            print(f"  [{i:>4}/{total}]  {label[:65]:<65}", end="", flush=True)

            # 1. Конвертируем в MP3
            mp3 = convert_to_mp3(src_file, tmp_dir)
            if not mp3:
                print(" CONV_FAIL")
                conv_fail += 1
                continue

            # 2. Название трека = имя файла без расширения (без ведущих цифр типа "01 - ")
            track_title = re.sub(r'^[\d\s\-_.]+', '', src_file.stem).strip() or src_file.stem

            # 3. Отправляем
            success = bot.send_audio(
                chat_id, thread_id,
                path      = mp3,
                title     = track_title,
                performer = subfolder,
                caption   = subfolder,     # подпись = название папки (аниме)
            )

            if success:
                print(" OK")
                ok_count += 1
            else:
                fail_count += 1

            # Удаляем временный файл чтоб не копить
            try:
                mp3.unlink()
            except Exception:
                pass

            if i < total:
                time.sleep(delay)

    finally:
        # Чистим временную папку
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{'═'*60}")
    print(f"  Отправлено:      {ok_count}/{total}")
    print(f"  Ошибки отправки: {fail_count}")
    print(f"  Ошибки конверт.: {conv_fail}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()
