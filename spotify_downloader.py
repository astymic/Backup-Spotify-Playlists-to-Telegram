#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import io

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
Spotify Playlist Downloader v3
================================
Скачивает треки из Spotify-плейлистов через yt-dlp.
Не требует Spotify API / Premium аккаунта.

Способы получения списка треков:
  1. Exportify CSV (РЕКОМЕНДУЕТСЯ) — exportify.net → Export → CSV-файл
  2. Текстовый файл "Исполнитель - Трек" (по одному в строке)

Зависимости:
    pip install yt-dlp
    winget install ffmpeg  (или https://ffmpeg.org)
"""

import argparse
import csv
import json
import re
import shutil
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime


# ──────────────────────────────────────────────────────────────────────────────
# Цвета
# ──────────────────────────────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m";  BOLD   = "\033[1m";  DIM    = "\033[2m"
    GREEN  = "\033[92m"; YELLOW = "\033[93m";  RED    = "\033[91m"
    CYAN   = "\033[96m"; BLUE   = "\033[94m"

def banner():
    print(f"""{C.CYAN}{C.BOLD}
+──────────────────────────────────────────────────────+
|        >>  Spotify Playlist Downloader  v3  <<       |
|         Exportify CSV  +  yt-dlp  (no API key)       |
+──────────────────────────────────────────────────────+
{C.RESET}""")

def info(m): print(f"  {C.CYAN}[i]{C.RESET}  {m}")
def ok(m):   print(f"  {C.GREEN}[+]{C.RESET}  {m}")
def warn(m): print(f"  {C.YELLOW}[!]{C.RESET}  {m}")
def err(m):  print(f"  {C.RED}[-]{C.RESET}  {m}", file=sys.stderr)
def step(n, t, m): print(f"\n{C.BLUE}[{n}/{t}]{C.RESET} {C.BOLD}{m}{C.RESET}")
def dim(m):  print(f"       {C.DIM}{m}{C.RESET}")


# ──────────────────────────────────────────────────────────────────────────────
# Загрузка треков
# ──────────────────────────────────────────────────────────────────────────────

def load_from_csv(path: Path) -> list[dict]:
    """CSV из Exportify (exportify.net)."""
    tracks = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_l = {k.lower().strip(): v.strip() for k, v in row.items() if k}
            artist = (
                row_l.get("artist name(s)") or row_l.get("artist names") or
                row_l.get("artist name")    or row_l.get("artist") or "Unknown"
            )
            title = (
                row_l.get("track name") or row_l.get("title") or
                row_l.get("name") or ""
            )
            if title:
                tracks.append({
                    "title":   title,
                    "artists": [a.strip() for a in artist.split(",")],
                    "album":   row_l.get("album name", ""),
                })
    return tracks


def load_from_txt(path: Path) -> list[dict]:
    """Текстовый файл: Исполнитель - Трек (по одному в строке)."""
    tracks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " - " in line:
                a, t = line.split(" - ", 1)
                tracks.append({"title": t.strip(), "artists": [a.strip()], "album": ""})
            else:
                tracks.append({"title": line, "artists": ["Unknown"], "album": ""})
    return tracks


# ──────────────────────────────────────────────────────────────────────────────
# Скачивание: yt-dlp → YouTube Music
# ──────────────────────────────────────────────────────────────────────────────

def sanitize(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def download_track(track: dict, output_dir: Path, fmt: str, quality: str) -> bool:
    artists  = ", ".join(track.get("artists", ["Unknown"]))
    title    = track.get("title", "Unknown")
    query    = f"{artists} - {title}"
    filename = sanitize(f"{artists} - {title}")
    out_tmpl = str(output_dir / f"{filename}.%(ext)s")
    final    = output_dir / f"{filename}.{fmt}"

    if final.exists():
        dim("пропуск (уже скачан)")
        return True

    cmd = [
        sys.executable, "-m", "yt_dlp",
        f"ytsearch1:{query}",
        "--extract-audio",
        "--audio-format",  fmt,
        "--audio-quality", f"{quality}k",
        "--output",        out_tmpl,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--embed-thumbnail",
        "--add-metadata",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode == 0


def save_tracklist(tracks: list[dict], output_dir: Path):
    path = output_dir / "tracklist.txt"
    with open(path, "w", encoding="utf-8") as f:
        for t in tracks:
            artists = ", ".join(t["artists"])
            f.write(f"{artists} - {t['title']}\n")
    info(f"Список сохранён: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        prog="spotify_downloader.py",
        description="Скачать Spotify-плейлист через yt-dlp (без API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
СПОСОБЫ ИСПОЛЬЗОВАНИЯ:
  1. Через Exportify CSV (РЕКОМЕНДУЕТСЯ):
       python spotify_downloader.py --from-csv playlist.csv

  2. Через текстовый файл (Artist - Title):
       python spotify_downloader.py --from-file tracks.txt

КАК ПОЛУЧИТЬ CSV (Exportify):
  1. Открыть https://exportify.net
  2. Войти через Spotify
  3. Нажать Export рядом с плейлистом
  4. Скачать CSV-файл
  5. python spotify_downloader.py --from-csv MY_PLAYLIST.csv
""",
    )

    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-csv",  "-C", metavar="FILE",
                     help="CSV-файл из Exportify (exportify.net)")
    src.add_argument("--from-file", "-F", metavar="FILE",
                     help="Текстовый файл 'Исполнитель - Трек'")

    p.add_argument("--output",    "-o", default="./downloads",
                   help="Папка для сохранения (по умолч.: ./downloads)")
    p.add_argument("--format",    "-f", default="mp3",
                   choices=["mp3", "flac", "ogg", "opus", "m4a"],
                   help="Формат аудио (по умолч.: mp3)")
    p.add_argument("--quality",   "-q", default="320",
                   choices=["128", "192", "256", "320"],
                   help="Битрейт kbps (по умолч.: 320)")
    p.add_argument("--delay",     type=float, default=0.0,
                   help="Пауза между треками (по умолч.: 0 при параллельной загрузке)")
    p.add_argument("--workers",   type=int, default=4,
                   help="Кол-во параллельных загрузок (по умолч.: 4)")
    p.add_argument("--save-list", action="store_true",
                   help="Сохранить список треков в tracklist.txt")
    return p.parse_args()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    banner()
    args = parse_args()
    total = 3
    cur   = 0

    # ── 1. Загрузка треков ───────────────────────────────────────────────────
    cur += 1
    step(cur, total, "Загрузка списка треков")

    if args.from_csv:
        fp = Path(args.from_csv)
        if not fp.exists():
            err(f"Файл не найден: {fp}"); sys.exit(1)
        tracks = load_from_csv(fp)
        ok(f"Загружено из CSV: {len(tracks)} треков")
    else:
        fp = Path(args.from_file)
        if not fp.exists():
            err(f"Файл не найден: {fp}"); sys.exit(1)
        tracks = load_from_txt(fp)
        ok(f"Загружено из файла: {len(tracks)} треков")

    if not tracks:
        warn("Список треков пуст. Проверьте файл."); sys.exit(0)

    for i, t in enumerate(tracks[:8], 1):
        dim(f"{i:>3}. {', '.join(t['artists'])} - {t['title']}")
    if len(tracks) > 8:
        dim(f"       ... и ещё {len(tracks) - 8}")

    # ── 2. Подготовка ────────────────────────────────────────────────────────
    cur += 1
    step(cur, total, "Подготовка")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    info(f"Папка:  {output_dir.resolve()}")
    info(f"Формат: {args.format.upper()} @ {args.quality} kbps")

    if args.save_list:
        save_tracklist(tracks, output_dir)

    if not shutil.which("ffmpeg"):
        warn("ffmpeg не найден — установите: winget install ffmpeg")

    # ── 3. Скачивание ────────────────────────────────────────────────────────
    cur += 1
    workers = min(args.workers, len(tracks))
    step(cur, total, f"Скачивание {len(tracks)} треков  [{C.CYAN}x{workers} потока{C.RESET}]")
    print()

    ok_count = fail_count = 0
    print_lock = threading.Lock()
    counters   = {"ok": 0, "fail": 0}
    start      = datetime.now()

    def download_one(idx_track: tuple[int, dict]) -> bool:
        i, track  = idx_track
        label     = f"{', '.join(track['artists'])} - {track['title']}"
        prefix    = f"  [{i:>3}/{len(tracks)}]"
        success   = download_track(track, output_dir, args.format, args.quality)
        status    = f" {C.GREEN}OK{C.RESET}" if success else f" {C.RED}FAIL{C.RESET}"
        with print_lock:
            print(f"{C.CYAN}{prefix}{C.RESET} {label[:60]:<60}{status}")
        return success

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(download_one, (i, t)): i
                   for i, t in enumerate(tracks, 1)}
        for fut in as_completed(futures):
            if fut.result():
                counters["ok"]   += 1
            else:
                counters["fail"] += 1

    ok_count   = counters["ok"]
    fail_count = counters["fail"]

    # ── Итог ─────────────────────────────────────────────────────────────────
    elapsed = datetime.now() - start
    mins, secs = divmod(int(elapsed.total_seconds()), 60)
    print(f"\n{'─'*58}")
    ok(f"Скачано:    {ok_count}/{len(tracks)}  |  {mins}мин {secs}сек")
    if fail_count:
        warn(f"Не удалось: {fail_count} треков — запустите повторно, пропущенные скачаются")
    ok(f"Папка:      {output_dir.resolve()}")

    log_path = output_dir / "download_log.txt"
    with open(log_path, "a", encoding="utf-8") as f:
        ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        src = args.from_csv or args.from_file or "?"
        f.write(f"[{ts}] SRC={src}  OK={ok_count}  FAIL={fail_count}  FMT={args.format}\n")


if __name__ == "__main__":
    main()
