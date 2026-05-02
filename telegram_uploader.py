#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
telegram_uploader.py
=====================
Загружает плейлисты в Telegram-группу с Topics (Forum-режим).

Структура папок:
    Playlists/
        My Playlist 1/        ← папка с .mp3 файлами
            Artist - Title.mp3
            ...
        My Playlist 2/
            ...
    Playlists_CSV/
        My Playlist 1.csv     ← CSV из Exportify (определяет порядок)
        My Playlist 2.csv

Результат в Telegram:
    Группа
    ├── 📌 My Playlist 1  (Topic)
    │       1. Artist - Title.mp3
    │       2. ...
    └── 📌 My Playlist 2  (Topic)
            ...

Настройка:
    1. Создать бота через @BotFather → скопировать TOKEN
    2. Добавить бота в группу как администратора (права: Manage Topics + Post Messages)
    3. Включить Topics в настройках группы (Edit → Topics → включить)
    4. Получить CHAT_ID группы (см. SETUP.md)
    5. Заполнить config.json
    6. python telegram_uploader.py
"""

import csv
import json
import os
import re
import sys
import time
import io
from pathlib import Path

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import requests
except ImportError:
    print("Установите: pip install requests")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Конфигурация
# ──────────────────────────────────────────────────────────────────────────────

CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        default = {
            "BOT_TOKEN":      "ВАШ_ТОКЕН_БОТА",
            "CHAT_ID":        -1001234567890,
            "PLAYLISTS_DIR":  "./Playlists",
            "CSV_DIR":        "./Playlists_CSV",
            "DELAY_SECONDS":   5,
            "AUDIO_FORMAT":   "mp3"
        }
        CONFIG_FILE.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[!] Создан config.json — заполните его и запустите снова.")
        sys.exit(0)

    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if cfg["BOT_TOKEN"] == "ВАШ_ТОКЕН_БОТА":
        print("[!] Заполните BOT_TOKEN и CHAT_ID в config.json")
        sys.exit(1)
    return cfg


# ──────────────────────────────────────────────────────────────────────────────
# Telegram Bot API
# ──────────────────────────────────────────────────────────────────────────────

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.base  = f"https://api.telegram.org/bot{token}"
        self._test_connection()

    def _api(self, method: str, data: dict = None, files=None, timeout=120) -> dict:
        url = f"{self.base}/{method}"
        resp = requests.post(url, data=data, files=files, timeout=timeout)
        result = resp.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API error: {result.get('description', result)}")
        return result["result"]

    def _test_connection(self):
        me = self._api("getMe")
        print(f"  [+] Бот подключён: @{me['username']}")

    def create_topic(self, chat_id: int, name: str, icon_color: int = 7322096) -> int:
        """Создаёт Forum Topic. Возвращает message_thread_id."""
        result = self._api("createForumTopic", {
            "chat_id":    chat_id,
            "name":       name[:128],   # макс. 128 символов
            "icon_color": icon_color,
        })
        return result["message_thread_id"]

    def send_audio(self, chat_id: int, thread_id: int, audio_path: Path,
                   title: str, performer: str) -> bool:
        """Отправляет аудио-файл в топик."""
        with open(audio_path, "rb") as f:
            try:
                self._api(
                    "sendAudio",
                    data={
                        "chat_id":           chat_id,
                        "message_thread_id": thread_id,
                        "title":             title[:64],
                        "performer":         performer[:64],
                    },
                    files={"audio": (audio_path.name, f, "audio/mpeg")},
                    timeout=180,
                )
                return True
            except Exception as e:
                print(f"    [-] Ошибка отправки: {e}")
                return False

    def send_message(self, chat_id: int, thread_id: int, text: str):
        self._api("sendMessage", {
            "chat_id":           chat_id,
            "message_thread_id": thread_id,
            "text":              text[:4096],
        })


# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────

def sanitize(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()

def read_csv_order(csv_path: Path) -> list[dict]:
    """Читает CSV из Exportify → возвращает список треков в порядке плейлиста."""
    tracks = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_l = {k.lower().strip(): v.strip() for k, v in row.items() if k}
            artist = (
                row_l.get("artist name(s)") or row_l.get("artist names") or
                row_l.get("artist name")    or row_l.get("artist") or "Unknown"
            )
            title = row_l.get("track name") or row_l.get("title") or row_l.get("name") or ""
            if title:
                tracks.append({
                    "title":  title,
                    "artist": artist.split(",")[0].strip(),   # первый исполнитель
                    "artists": artist,
                })
    return tracks

def find_audio_file(folder: Path, artists: str, title: str, fmt: str) -> Path | None:
    """
    Ищет аудио-файл. Приоритет:
      1. Точное совпадение 'Artist - Title.mp3'
      2. Файл содержит и artist, и title
      3. Файл содержит title как отдельное слово
    Файлы перебираются в отсортированном порядке — гарантирует воспроизводимость.
    """
    def norm(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r'[\\/*?:"<>|]', "_", s)
        s = re.sub(r'\s+', ' ', s)
        return s

    primary_artist = artists.split(",")[0].strip()
    title_n        = norm(title)
    artist_n       = norm(primary_artist)
    all_artists_n  = norm(artists)

    all_files = sorted(folder.glob(f"*.{fmt}"))   # сортировка для детерминизма

    # 1. Точное совпадение filename
    for f in all_files:
        stem = norm(f.stem)
        if stem in (f"{artist_n} - {title_n}", f"{all_artists_n} - {title_n}"):
            return f

    # 2. Файл содержит и artist, и title
    for f in all_files:
        stem = norm(f.stem)
        if title_n in stem and (artist_n in stem or all_artists_n in stem):
            return f

    # 3. Только title — как отдельное слово (не часть другого слова)
    for f in all_files:
        stem = norm(f.stem)
        if re.search(r'(?<![a-z])' + re.escape(title_n) + r'(?![a-z])', stem):
            return f

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Основная логика
# ──────────────────────────────────────────────────────────────────────────────

def upload_playlist(bot: TelegramBot, cfg: dict,
                    playlist_dir: Path, csv_path: Path | None):
    name      = playlist_dir.name
    chat_id   = cfg["CHAT_ID"]
    delay     = cfg.get("DELAY_SECONDS", 5)
    fmt       = cfg.get("AUDIO_FORMAT", "mp3")

    print(f"\n{'─'*60}")
    print(f"  Плейлист: {name}")
    print(f"{'─'*60}")

    # 1. Создаём топик
    print(f"  [>] Создаю топик '{name}'...")
    thread_id = bot.create_topic(chat_id, name)
    print(f"  [+] Топик создан (thread_id={thread_id})")
    time.sleep(1)

    # 2. Определяем порядок треков
    if csv_path and csv_path.exists():
        tracks = read_csv_order(csv_path)
        print(f"  [i] Порядок из CSV: {len(tracks)} треков")
    else:
        # Нет CSV — берём все файлы из папки в алфавитном порядке
        files  = sorted(playlist_dir.glob(f"*.{fmt}"))
        tracks = [{"title": f.stem, "artist": "", "artists": ""} for f in files]
        print(f"  [i] CSV не найден, загружаю {len(tracks)} файлов из папки")

    # 3. Загружаем треки по порядку
    ok = fail = skip = 0
    for i, track in enumerate(tracks, 1):
        title   = track["title"]
        artist  = track.get("artist", "")
        artists = track.get("artists", artist)

        audio = find_audio_file(playlist_dir, artists or title, title, fmt)

        if not audio:
            print(f"  [{i:>3}/{len(tracks)}] {artist} - {title[:40]} ... ФАЙЛ НЕ НАЙДЕН")
            skip += 1
            continue

        size_mb = audio.stat().st_size / 1_048_576
        print(f"  [{i:>3}/{len(tracks)}] {artist} - {title[:35]:<35} → {audio.name[:35]} ({size_mb:.1f}MB)", end="", flush=True)

        success = bot.send_audio(
            chat_id, thread_id, audio,
            title=title,
            performer=artist or artists,
        )

        if success:
            print(" OK")
            ok += 1
        else:
            print(" FAIL")
            fail += 1

        time.sleep(delay)   # пауза после каждого трека (в т.ч. последнего)

    print(f"\n  Итог: OK={ok}  FAIL={fail}  SKIP={skip}/{len(tracks)}")
    return ok, fail, skip


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║        >>  Telegram Playlist Uploader  <<            ║
║         Playlists → Forum Topics → Audio             ║
╚══════════════════════════════════════════════════════╝
""")
    cfg = load_config()
    bot = TelegramBot(cfg["BOT_TOKEN"])

    playlists_dir = Path(cfg["PLAYLISTS_DIR"])
    csv_dir       = Path(cfg["CSV_DIR"])

    if not playlists_dir.exists():
        print(f"[-] Папка Playlists не найдена: {playlists_dir}")
        sys.exit(1)

    # Находим все папки плейлистов
    playlist_folders = sorted([d for d in playlists_dir.iterdir() if d.is_dir()])
    if not playlist_folders:
        print(f"[-] В папке {playlists_dir} нет подпапок с плейлистами")
        sys.exit(1)

    print(f"\n  Найдено папок: {len(playlist_folders)}")
    no_csv_list = [name.lower() for name in cfg.get("NO_CSV_FOLDERS", [])]
    to_upload   = []   # list of (folder, csv_path_or_None)

    for d in playlist_folders:
        files_count   = len(list(d.glob(f"*.{cfg.get('AUDIO_FORMAT','mp3')}")))
        is_no_csv     = d.name.lower() in no_csv_list

        if is_no_csv:
            print(f"    [+] {d.name}  ({files_count} файлов)  ← без CSV (алфавитный порядок)")
            to_upload.append((d, None))
            continue

        csv_candidates = [csv_dir / f"{d.name}.csv", csv_dir / f"{d.name.lower()}.csv"]
        csv_found = next((c for c in csv_candidates if c.exists()), None)

        if csv_found:
            print(f"    [+] {d.name}  ({files_count} файлов)  ← {csv_found.name}")
            to_upload.append((d, csv_found))
        else:
            print(f"    [-] {d.name}  — нет CSV, пропуск")

    if not to_upload:
        print("\n  [-] Нет плейлистов для загрузки.")
        sys.exit(0)

    print(f"\n  Будет загружено: {len(to_upload)} плейлист(ов)")
    print(f"  Группа: {cfg['CHAT_ID']}")
    input("\n  Нажмите Enter для начала загрузки... (Ctrl+C для отмены)")

    total_ok = total_fail = total_skip = 0

    for folder, csv_path in to_upload:
        ok, fail, skip = upload_playlist(bot, cfg, folder, csv_path)
        total_ok   += ok
        total_fail += fail
        total_skip += skip
        time.sleep(2)

    print(f"\n{'═'*60}")
    print(f"  ИТОГО: OK={total_ok}  FAIL={total_fail}  SKIP={total_skip}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()
