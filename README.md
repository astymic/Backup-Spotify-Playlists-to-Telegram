# Backup Spotify Playlists to Telegram

Скачивает Spotify-плейлисты через yt-dlp и выгружает в Telegram-группу с Topics.

## Скрипты

| Файл | Назначение |
|---|---|
| `spotify_downloader.py` | Скачать плейлист по CSV из Exportify |
| `telegram_uploader.py` | Выгрузить папки с треками в Telegram Topics |
| `anime_uploader.py` | Выгрузить аниме OST (папки с подпапками) в один Topic |

## Быстрый старт

### 1. Установка зависимостей
```bash
pip install yt-dlp requests
winget install ffmpeg
```

### 2. Настройка конфига
Скопируйте `config.json`, заполните токен и ID группы:
```json
{
  "BOT_TOKEN": "токен от @BotFather",
  "CHAT_ID": -1001234567890,
  "PLAYLISTS_DIR": "./Playlists",
  "CSV_DIR": "./Playlists_CSV",
  "DELAY_SECONDS": 5,
  "AUDIO_FORMAT": "mp3",
  "NO_CSV_FOLDERS": [],
  "ANIME_DIR": "путь/к/папке/с/аниме",
  "ANIME_TOPIC_NAME": "Anime Openings"
}
```

### 3. Скачать плейлист
1. Экспортировать CSV на [exportify.net](https://exportify.net)
2. Запустить:
```bash
python spotify_downloader.py --from-csv MY_PLAYLIST.csv --output ./Playlists/MyPlaylist
```

### 4. Выгрузить в Telegram
```bash
python telegram_uploader.py   # плейлисты по CSV
python anime_uploader.py      # аниме OST
```

## Структура папок
```
├── Playlists/
│   └── My Playlist/       ← mp3 файлы
├── Playlists_CSV/
│   └── My Playlist.csv    ← из Exportify
├── spotify_downloader.py
├── telegram_uploader.py
├── anime_uploader.py
└── config.json            ← НЕ коммитить!
```

## Настройка Telegram бота
Подробнее — в [SETUP_TELEGRAM.md](SETUP_TELEGRAM.md)
