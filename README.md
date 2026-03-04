# Telegram Anonymous Questions Bot

> Telegram-бот для анонимных вопросов с модерацией. Участники группы задают вопросы боту в личку — он публикует их анонимно в выбранный топик группы после одобрения администратором.

## Возможности

- **Анонимность** — имя автора нигде не фигурирует
- **Модерация** — каждый вопрос проходит проверку до публикации
- **Только участники** — посторонние не могут задавать вопросы
- **Динамическая настройка группы** — `/set_topic` без редактирования `.env`
- **Rate limiting** — скользящее окно, настраивается через переменную окружения
- **Удаление вопросов** — авторы могут удалять свои вопросы

## Архитектура

```
Телеграм API (long polling)
          │
          ▼
     src/main.py
    ┌──────┴──────┐
    │             │
handlers/      handlers/
private.py     group.py
(личка)        (команды)
    │
    ├── services/membership.py   ← проверка участника группы
    ├── services/rate_limiter.py ← лимит запросов
    ├── services/anonymizer.py   ← очистка контента
    ├── services/publisher.py    ← публикация в топик
    └── database.py              ← SQLite (aiosqlite)
```

## Структура проекта

```
telegram-anon-bot/
├── src/
│   ├── main.py              # точка входа
│   ├── config.py            # конфигурация через pydantic-settings
│   ├── database.py          # все операции с SQLite
│   ├── handlers/
│   │   ├── private.py       # обработка личных сообщений
│   │   ├── group.py         # /set_topic, /settings
│   │   └── callback.py      # inline-кнопки модерации и удаления
│   └── services/
│       ├── membership.py    # проверка членства в группе
│       ├── rate_limiter.py  # скользящее окно
│       ├── anonymizer.py    # подготовка контента
│       └── publisher.py     # публикация в топик
├── .env.example             # шаблон конфигурации
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── anon-bot.service         # systemd unit
```

## Быстрый старт

### 1. Создать бота

1. Открыть [@BotFather](https://t.me/BotFather)
2. Отправить `/newbot`, получить **BOT_TOKEN**
3. Отключить приватность группы: `/setprivacy` → бот → **Disable**

### 2. Узнать свой Telegram ID

Отправить сообщение боту [@userinfobot](https://t.me/userinfobot) — он вернёт ваш **ADMIN_ID**.

### 3. Узнать ID группы

Добавить [@RawDataBot](https://t.me/RawDataBot) в группу — он покажет `chat.id` (отрицательное число).

### 4. Настроить окружение

```bash
git clone https://github.com/Bondartsov/telegram-anon-bot.git
cd telegram-anon-bot

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Заполнить BOT_TOKEN, GROUP_ID, ADMIN_ID в .env
```

### 5. Запустить

```bash
# Разработка
python -m src.main

# Docker
docker-compose up -d
```

### 6. Настроить топик для вопросов

1. Добавить бота в группу как **администратора**
2. Зайти в нужный топик
3. Отправить `/set_topic` — бот запомнит этот топик в БД
4. С этого момента все вопросы будут публиковаться сюда

> `/set_topic` можно вызывать в любой момент для смены топика — изменения вступают в силу немедленно, без перезапуска.

## Команды

### Для пользователей (личка)

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и инструкция |
| `/delete` | Удалить свой недавний вопрос |
| Текст | Отправить анонимный вопрос |
| Фото + подпись | Отправить вопрос с фото |

### Для администратора

| Команда | Где | Описание |
|---------|-----|----------|
| `/set_topic` | В топике группы | Назначить топик для вопросов |
| `/settings` | В группе | Текущие настройки бота |
| `/mod_history` | Личка | История модерации |
| `/stats` | Личка | Статистика вопросов |

## Переменные окружения

| Переменная | Обязательная | Описание |
|------------|:---:|---------|
| `BOT_TOKEN` | ✅ | Токен бота от @BotFather |
| `GROUP_ID` | ✅ | ID группы (отрицательное число) |
| `ADMIN_ID` | ✅ | Ваш Telegram user ID |
| `RATE_LIMIT` | ❌ | Вопросов в час на пользователя (по умолч.: 10) |
| `LOG_LEVEL` | ❌ | Уровень логов: DEBUG/INFO/WARNING (по умолч.: INFO) |

## Деплой на Linux (systemd)

```bash
# Первый деплой
./deploy.sh --first-run

# Обновление кода
./deploy.sh

# Просмотр логов
journalctl -u anon-bot -f

# Статус
systemctl status anon-bot
```

## Безопасность

- Membership check — только участники группы могут задавать вопросы
- Rate limiting — скользящее окно предотвращает спам
- Модерация — ни один вопрос не публикуется без одобрения
- Анонимность — `user_id` хранится в БД, но не передаётся в группу
- `.env` и `data/*.db` исключены из git

## Лицензия

MIT
