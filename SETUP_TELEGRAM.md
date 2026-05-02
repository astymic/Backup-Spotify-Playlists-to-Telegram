# Настройка Telegram Uploader

## Шаг 1 — Создать Telegram бота

1. Открыть [@BotFather](https://t.me/BotFather) в Telegram
2. Написать `/newbot`
3. Придумать имя (например: `My Music Bot`)
4. Придумать username (например: `mymusicupload_bot`)
5. Скопировать **токен** — выглядит так: `7123456789:AAHzFN...`

---

## Шаг 2 — Настроить группу

1. В вашей группе → **Edit Group** → **Topics** → включить
2. Добавить бота в группу
3. Сделать бота **администратором** с правами:
   - ✅ **Manage Topics**
   - ✅ **Post Messages**
   - ✅ **Send Media** (для файлов)

---

## Шаг 3 — Узнать CHAT_ID группы

Открыть в браузере (вставить свой токен бота):
```
https://api.telegram.org/bot<ВАШ_ТОКЕН>/getUpdates
```

Отправить любое сообщение в группу, обновить страницу и найти:
```json
"chat": { "id": -1001234567890, ... }
```

Это и есть ваш **CHAT_ID** (отрицательное число, начинается с -100).

> **Альтернатива:** добавить в группу [@userinfobot](https://t.me/userinfobot) — он сразу покажет ID.

---

## Шаг 4 — Настроить config.json

Открыть `config.json` и заполнить:

```json
{
  "BOT_TOKEN":     "7123456789:AAHzFN...",
  "CHAT_ID":       -1001234567890,
  "PLAYLISTS_DIR": "./Playlists",
  "CSV_DIR":       "./Playlists_CSV",
  "DELAY_SECONDS": 5,
  "AUDIO_FORMAT":  "mp3"
}
```

| Параметр | Описание |
|---|---|
| `BOT_TOKEN` | Токен от @BotFather |
| `CHAT_ID` | ID группы (отрицательное число) |
| `PLAYLISTS_DIR` | Папка с подпапками плейлистов |
| `CSV_DIR` | Папка с CSV-файлами из Exportify |
| `DELAY_SECONDS` | Пауза между треками (5с — безопасно, 3с — быстрее) |
| `AUDIO_FORMAT` | Формат файлов: `mp3`, `flac`, `m4a` |

---

## Шаг 5 — Структура папок

```
tracks backup/
├── Playlists/
│   ├── Prompto/              ← название папки = название топика
│   │   ├── Prompto - RTX.mp3
│   │   ├── Mvko - Baryon Mode.mp3
│   │   └── ...
│   └── Chill Vibes/
│       └── ...
├── Playlists_CSV/
│   ├── Prompto.csv           ← имя CSV = имя папки!
│   └── Chill Vibes.csv
├── spotify_downloader.py
├── telegram_uploader.py
└── config.json
```

> ⚠️ CSV файл должен называться **точно так же**, как папка плейлиста.

---

## Шаг 6 — Запуск

```bash
pip install requests
python telegram_uploader.py
```

Скрипт:
1. Покажет список найденных плейлистов
2. Спросит подтверждение
3. Создаст топики в группе
4. Загрузит треки по порядку из CSV

---

## Лимиты Telegram

| Ограничение | Значение |
|---|---|
| Макс. размер файла | **50 MB** (через Bot API) |
| Сообщений в минуту | ~20 в группу |
| Рекомендуемая пауза | 5 секунд |

> Если файл > 50 MB — скрипт выведет `FAIL`. Такие файлы нужно скачать в формате `mp3` (не flac).
