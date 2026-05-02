# Backup Spotify Playlists to Telegram

Downloads Spotify playlists via yt-dlp and uploads them to a Telegram group with Topics (Forum mode).

## Scripts

| File | Purpose |
|---|---|
| `spotify_downloader.py` | Download a playlist from a CSV exported via Exportify |
| `telegram_uploader.py` | Upload track folders to Telegram Topics |
| `anime_uploader.py` | Upload anime OSTs (nested folders) into a single Topic |

## Quick Start

### 1. Install dependencies
```bash
pip install yt-dlp requests
winget install ffmpeg
```

### 2. Configure
Copy `config.example.json` to `config.json` and fill in your bot token and group ID:
```json
{
  "BOT_TOKEN": "token from @BotFather",
  "CHAT_ID": -1001234567890,
  "PLAYLISTS_DIR": "./Playlists",
  "CSV_DIR": "./Playlists_CSV",
  "DELAY_SECONDS": 5,
  "AUDIO_FORMAT": "mp3",
  "NO_CSV_FOLDERS": [],
  "ANIME_DIR": "path/to/Openings - Endings-OSTs",
  "ANIME_TOPIC_NAME": "Anime Openings"
}
```

| Key | Description |
|---|---|
| `BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `CHAT_ID` | Your Telegram group ID (negative number) |
| `PLAYLISTS_DIR` | Folder containing playlist subfolders |
| `CSV_DIR` | Folder containing Exportify CSV files |
| `DELAY_SECONDS` | Delay between uploads (5s recommended) |
| `AUDIO_FORMAT` | Output format: `mp3`, `flac`, `m4a` |
| `NO_CSV_FOLDERS` | Folders to upload without CSV (alphabetical order) |
| `ANIME_DIR` | Path to your anime music folder |
| `ANIME_TOPIC_NAME` | Telegram topic name for anime uploads |

### 3. Download a playlist
1. Export a CSV at [exportify.net](https://exportify.net)
2. Run:
```bash
python spotify_downloader.py --from-csv MY_PLAYLIST.csv --output ./Playlists/MyPlaylist

# Options
python spotify_downloader.py --from-csv playlist.csv --format flac --quality 320
python spotify_downloader.py --from-csv playlist.csv --workers 4   # parallel downloads
```

### 4. Upload to Telegram
```bash
python telegram_uploader.py   # upload playlists (CSV-ordered)
python anime_uploader.py      # upload anime OSTs
```

## Folder Structure
```
├── Playlists/
│   └── My Playlist/          ← mp3 files go here
├── Playlists_CSV/
│   └── My Playlist.csv       ← exported from Exportify
├── spotify_downloader.py
├── telegram_uploader.py
├── anime_uploader.py
├── config.json               ← DO NOT commit (in .gitignore)
└── config.example.json       ← safe template to commit
```

## Telegram Bot Setup

### Create a bot
1. Open [@BotFather](https://t.me/BotFather) → `/newbot`
2. Copy the token

### Configure your group
1. Enable **Topics**: Group Settings → Edit → Topics → turn on
2. Add the bot as **Admin** with permissions:
   - ✅ Manage Topics
   - ✅ Post Messages
   - ✅ Send Media

### Get CHAT_ID
Open in browser (replace with your token):
```
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```
Send any message to the group, refresh, and find `"chat": { "id": -100... }`.

## Notes

- **File size limit**: Telegram Bot API allows up to **50 MB** per file. Most MP3s are well within this limit.
- **Rate limit**: ~20 messages/min per group. Use `DELAY_SECONDS: 5` or higher to stay safe.
- **Parallel downloads**: `--workers 4` (default) speeds up Spotify downloads ~4x. Reduce if YouTube starts blocking.
