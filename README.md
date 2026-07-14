# Telegram Anonymous Questions Bot

> **Telegram-бот для анонимных вопросов с модерацией.** Участники группы пишут боту в личные сообщения — бот публикует вопрос анонимно в заданный топик группы **только после одобрения администратором**. Имя автора нигде не раскрывается.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-26a5e4)](https://aiogram.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#-лицензия)

---

## 📑 Содержание

- [Обзор](#-обзор)
- [Ключевые свойства](#-ключевые-свойства)
- [Архитектура системы](#-архитектура-системы)
- [Жизненный цикл вопроса](#-жизненный-цикл-вопроса)
- [Схема базы данных](#-схема-базы-данных)
- [Команды и взаимодействия](#-команды-и-взаимодействия)
- [Модель анонимности и безопасности](#-модель-анонимности-и-безопасности)
- [Сервисный слой (API контракты)](#-сервисный-слой-api-контракты)
- [Конфигурация](#-конфигурация)
- [Быстрый старт](#-быстрый-старт)
- [Развёртывание](#-развёртывание)
- [Эксплуатация и операции](#-эксплуатация-и-операции)
- [Устранение неисправностей (FAQ)](#-устранение-неисправностей-faq)
- [Структура проекта](#-структура-проекта)
- [Лицензия](#-лицензия)

---

## 🎯 Обзор

Бот решает одну конкретную задачу: **позволить участникам сообщества задавать вопросы анонимно**, при этом сохраняя контроль качества через модерацию.

**Сценарий использования:** в группе (например, чат курса, конференции, сообщества) админ создаёт топик «Анонимные вопросы». Участники пишут боту в личку. Каждый вопрос проходит проверку администратора → публикуется в топик без указания автора.

| Параметр | Значение |
|----------|----------|
| **Язык реализации** | Python 3.10+ |
| **Фреймворк** | [aiogram](https://aiogram.dev/) 3.x (async) |
| **Хранилище** | SQLite (через `aiosqlite`) |
| **Конфигурация** | `pydantic-settings` + `.env` |
| **Получение обновлений** | Long polling (один процесс) |
| **Деплой** | systemd / Docker / docker-compose |
| **Состояние** | Бесконечный цикл polling, in-memory rate limiter |

---

## ✨ Ключевые свойства

| Свойство | Реализация |
|----------|------------|
| 🔒 **Анонимность** | `user_id` хранится в БД для модерации/удаления, но **никогда** не передаётся в группу. В публикуемом сообщении нет имени автора. |
| ✅ **Обязательная модерация** | Каждый вопрос проходит статусы `pending → approved\|rejected`. Ничто не публикуется без явного одобрения. |
| 👥 **Только участники** | Перед сохранением вопроса проверяется членство автора в целевой группе через `getChatMember`. |
| ⏱ **Rate limiting** | Скользящее окно в памяти: по умолчанию 10 вопросов/час на пользователя. Состояние сбрасывается при перезапуске. |
| 🗑 **Самоудаление** | Автор может удалить свой опубликованный вопрос через `/delete` — сообщение удалится и из группы. |
| ⚙️ **Динамическая настройка** | Целевая группа+топик задаются командой `/set_topic` в группе — без правки `.env` и перезапуска. |

---

## 🏛 Архитектура системы

### Высокоуровневая схема

```
  ┌─────────────────────────────────────────────────────────┐
  │                    Telegram Bot API                      │
  │              (long polling: getUpdates)                  │
  └───────────────▲─────────────────────┬───────────────────┘
                  │ updates             │ send_message/photo/delete
                  │                     │
        ┌─────────┴─────────┐  ┌────────┴────────┐
        │  Private chatter  │  │   Group chat    │
        │  (авторы вопросов)│  │  (публикация)   │
        └─────────▲─────────┘  └────────▲────────┘
                  │                     │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │   src/main.py       │   ← точка входа
                  │   Dispatcher + 3    │
                  │   routers + db      │
                  │   middleware        │
                  └──┬──────┬──────┬───┘
                     │      │      │
            ┌────────┘      │      └────────┐
            ▼               ▼               ▼
      ┌──────────┐    ┌──────────┐    ┌──────────┐
      │ private  │    │  group   │    │ callback │
      │  .py     │    │  .py     │    │  .py     │
      │ handlers/│    │ handlers/│    │ handlers/│
      └────┬─────┘    └────┬─────┘    └────┬─────┘
           │               │               │
           └───────┬───────┴───────┬───────┘
                   │               │
           ┌───────▼───────┐ ┌─────▼──────────────┐
           │   services/   │ │   database.py      │
           │ • anonymizer  │ │   (aiosqlite)      │
           │ • membership  │ │   SQLite:          │
           │ • publisher   │ │   users, questions,│
           │ • rate_limiter│ │   group_configs    │
           └───────────────┘ └────────────────────┘
```

### Поток «автор отправляет вопрос»

```
[Автор в ЛС]
     │ текст или фото+подпись
     ▼
handle_question()  ──── handlers/private.py
     │
     ├─ 1. Rate limit check ────────► rate_limiter.check_limit()
     │     (если превышен → отказ с таймером)
     │
     ├─ 2. Extract & validate ──────► anonymizer.prepare_content()
     │                                  + validate_content()
     │     (если невалиден → отказ)
     │
     ├─ 3. Resolve target ──────────► database.get_latest_group_config()
     │     (group_id, topic_id)        (последний /set_topic)
     │     (если не настроено → отказ)
     │
     ├─ 4. Membership check ────────► membership.is_group_member()
     │     (если не участник → отказ)
     │
     ├─ 5. Save pending ────────────► database.save_pending_question()
     │     status='pending'
     │
     ├─ 6. Send to ADMIN ───────────► bot.send_message/photo
     │     + inline keyboard             (админ видит текст,
     │     [✅ Одобрить][❌ Отклонить]    но НЕ имя автора в группе)
     │
     ├─ 7. Notify author ───────────► "Отправлен на модерацию"
     │
     └─ 8. Record rate limit ───────► rate_limiter.record_submission()
           (последним — если шаг 6/7 упадёт, лимит не тратится)
```

### Поток «админ одобряет вопрос»

```
[ADMIN нажимает ✅ Одобрить]
     │ callback_data = "mod_approve:<question_id>"
     ▼
cb_mod_approve() ──── handlers/callback.py
     │
     ├─ проверка: callback.from_user.id == ADMIN_ID
     ├─ get_question_by_id() → status должен быть 'pending'
     │
     ├─ publish_question() ─────► publisher.py
     │     bot.send_message/photo(message_thread_id=topic_id)
     │     → message_id возвращается
     │
     ├─ approve_question() ────► database
     │     status='approved', topic_message_id=message_id
     │
     ├─ bot.send_message(user_id, "✅ Опубликован!")
     │     (уведомление автору, ошибки глушатся)
     │
     └─ edit admin message: "— ОДОБРЕНО" (кнопки убраны)
```

---

## 🔄 Жизненный цикл вопроса

```
                         ┌─────────────┐
                         │   (нет)     │
                         │  нет записи │
                         └──────┬──────┘
                                │ пользователь пишет боту
                                ▼
                         ┌─────────────┐  админ жмёт ❌
              ┌────────► │   pending   │ ◄───────────┐
              │          └──────┬──────┘             │
              │                 │ админ жмёт ✅      │
              │                 ▼                    │
              │          ┌─────────────┐              │
              │          │  approved   │              │
              │          └──────┬──────┘              │
              │                 │                     │
              │                 │ автор: /delete      │
              │                 ▼                     │
              │          ┌─────────────┐              │
              │          │ approved +  │              │
              │          │is_deleted=1 │              │
              │          └─────────────┘              │
              │                                       │
              │          ┌─────────────┐              │
              └──────────┤  rejected   ├──────────────┘
                 (нет)   └─────────────┘
```

| Статус | `is_deleted` | Значение | Сообщение в группе | Можно удалить через `/delete`? |
|--------|:---:|----------|:---:|:---:|
| `pending` | `0` | Ожидает решения админа | ❌ | ❌ |
| `approved` | `0` | Опубликован | ✅ | ✅ |
| `approved` | `1` | Удалён автором | ❌ (удалено) | ❌ |
| `rejected` | `0` | Отклонён админом | ❌ | ❌ |

> **Инвариант:** `/delete` (через `get_user_questions`) возвращает только `status='approved' AND is_deleted=0` за последние 24 часа. Это гарантирует наличие `topic_message_id` для удаления из группы.

---

## 🗄 Схема базы данных

SQLite, файл `data/bot.db`. Создаётся автоматически при первом запуске (`init_db`).

### Таблица `users`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `telegram_id` | `INTEGER PRIMARY KEY` | Telegram user ID |
| `username` | `TEXT` | @username (без @) |
| `first_name` | `TEXT` | Имя |
| `last_name` | `TEXT` | Фамилия |
| `created_at` | `TIMESTAMP` | По умолч. `CURRENT_TIMESTAMP` |

> Таблица существует в схеме, но `ensure_user()` в текущем коде не вызывается — пользователи неявно сохраняются только через связь `questions.user_id`. Зарезервирована для будущих функций.

### Таблица `questions` (основная)

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | `TEXT PRIMARY KEY` | UUID4 (генерируется при сохранении) |
| `user_id` | `INTEGER NOT NULL` | Telegram ID автора (FK → users) |
| `content` | `TEXT NOT NULL` | Текст вопроса |
| `media_type` | `TEXT` | `'photo'` или `NULL` |
| `media_file_id` | `TEXT` | Telegram file_id медиа или `NULL` |
| `group_id` | `INTEGER NOT NULL` | ID целевой группы |
| `topic_id` | `INTEGER NOT NULL` | ID топика (thread) |
| `topic_message_id` | `INTEGER` | ID сообщения в группе (заполняется при одобрении) |
| `status` | `TEXT` | `'pending'` (по умолч.) / `'approved'` / `'rejected'` |
| `created_at` | `TIMESTAMP` | По умолч. `CURRENT_TIMESTAMP` |
| `is_deleted` | `BOOLEAN` | По умолч. `FALSE` (soft delete) |

**Индексы:**
- `idx_questions_user_id` на `(user_id, created_at DESC)` — для `/delete`
- `idx_questions_deleted` на `(is_deleted, created_at DESC)`

### Таблица `group_configs`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `group_id` | `INTEGER PRIMARY KEY` | ID группы |
| `topic_id` | `INTEGER NOT NULL` | ID назначенного топика |
| `created_at` | `TIMESTAMP` | Время создания |
| `updated_at` | `TIMESTAMP` | Время последнего `/set_topic` |

> **«Активная цель публикации»** определяется как запись с максимальным `updated_at` (через `get_latest_group_config()`). Последний вызванный `/set_topic` побеждает.

---

## 🎛 Команды и взаимодействия

### Команды в личных сообщениях (боту в ЛС)

| Команда / действие | Кто | Поведение |
|--------------------|-----|-----------|
| `/start` | любой | Приветствие + краткая инструкция |
| `/delete` | любой автор | Inline-клавиатура из **ваших** последних ≤5 одобренных вопросов за 24 часа |
| `/mod_history` | **только `ADMIN_ID`** | Последние 15 модерированных вопросов со статусом |
| `/stats` | **только `ADMIN_ID`** | Счётчики: всего / одобрено / отклонено / ожидает |
| **Текстовое сообщение** | участник группы | Отправить анонимный вопрос (→ pending) |
| **Фото + подпись** | участник группы | Вопрос с фото (→ pending) |
| Видео/документ/стикер/войс/аудио | любой | ❌ Отклонено: "тип не поддерживается" |
| Фото без подписи | любой | ❌ Отклонено: "добавьте подпись" |
| Текст < 3 символов | любой | ❌ Отклонено: "слишком короткий" |
| Текст > 4000 символов | любой | ❌ Отклонено: "слишком длинный" |

### Команды в группе

| Команда | Кто | Условие | Поведение |
|---------|-----|---------|-----------|
| `/set_topic` | админ группы | **внутри топика** | Назначает текущий thread целью публикации |
| `/set_topic` | не админ | — | ❌ "Только администраторы" |
| `/set_topic` | админ | вне топика | ❌ "Используйте внутри темы" |
| `/settings` | любой | — | Текущая конфигурация бота для группы |
| `/start` | любой | — | Инфо о боте + команды для админов |

### Inline-кнопки (callback queries)

| `callback_data` | Кто может нажать | Действие |
|-----------------|------------------|----------|
| `mod_approve:<uuid>` | `ADMIN_ID` | Одобрить → опубликовать в группу → уведомить автора |
| `mod_reject:<uuid>` | `ADMIN_ID` | Отклонить → уведомить автора |
| `del_select:<uuid>` | автор вопроса | Показать диалог подтверждения удаления |
| `del_confirm:<uuid>` | автор вопроса | Удалить из группы + soft delete в БД |
| `del_cancel` | автор вопроса | Отменить удаление |

> Кнопки модерации проверяют `callback.from_user.id == ADMIN_ID`. Кнопки удаления неявно защищены ownership-проверкой: `delete_question()` и `get_user_questions()` фильтруют по `user_id`.

---

## 🔐 Модель анонимности и безопасности

### Что видит каждая сторона

| Сторона | Что видит | Чего **не** видит |
|---------|-----------|-------------------|
| **Автор** | свои вопросы, статусы, уведомления | чужие вопросы |
| **Админ (`ADMIN_ID`)** | текст **каждого** pending-вопроса, `user_id` (в БД/`/mod_history`/`/stats`), фото | — |
| **Участники группы** | только опубликованные тексты без имени автора | авторов, отклонённые, pending |
| **Telegram API** | весь трафик (включая `user_id`) | — |

> ⚠️ **Важно про анонимность:** бот скрывает автора от **участников группы**, но **не от администратора**. Админ с доступом к БД/логам видит `user_id` каждого вопроса. Это особенность дизайна (нужна для модерации), а не баг.

### Защитные механизмы

| Механизм | Где | Что делает |
|----------|-----|------------|
| **Moderation gate** | `cb_mod_approve` | Ничто не публикуется без явного одобрения |
| **Membership check** | `is_group_member` | Только `member/administrator/creator/restricted` могут слать вопросы |
| **Rate limiting** | `RateLimiter` | Скользящее окно 10/час (настраивается), in-memory |
| **Ownership check** | `delete_question`, `get_user_questions` | `WHERE user_id = ?` — нельзя удалить чужое |
| **Admin guard** | `cb_mod_approve/reject`, `/mod_history`, `/stats` | `if from_user.id != ADMIN_ID: reject` |
| **`.gitignore`** | репозиторий | `.env`, `*.log`, `data/*.db` исключены из git |
| **Non-root Docker** | `Dockerfile` | Процесс выполняется от `botuser` |
| **systemd hardening** | `anon-bot.service` | `NoNewPrivileges=true` |

### Известные ограничения

- **Rate limiter в памяти** — счётчик сбрасывается при перезапуске процесса. Это означает, что перезапуск бота даёт всем пользователям свежий лимит.
- **`ADMIN_ID` хранится в `.env`** — это единственный администратор. Множественные админы не поддерживаются.
- **Long polling = один процесс** — нельзя запускать две копии бота одновременно (конкуренция за `getUpdates` → Telegram flood control).
- **`media_file_id` имеет срок жизни** — Telegram хранит file_id продолжительное время, но фото, отправленные очень давно, могут стать недоступными для повторной пересылки.

---

## 🧩 Сервисный слой (API контракты)

### `services/anonymizer.py`

```python
@dataclass
class AnonContent:
    text: str
    media_type: Optional[str] = None     # 'photo' | None
    media_file_id: Optional[str] = None

    @property
    def has_content(self) -> bool: ...   # True если есть текст или медиа
    @property
    def is_photo(self) -> bool: ...      # True если photo + file_id
    @property
    def is_text_only(self) -> bool: ...

def prepare_content(message: Message) -> AnonContent
    # Извлекает текст/фото. ValueError для неподдерживаемых типов.

def validate_content(content, max_length=4000) -> tuple[bool, str]
    # (is_valid, error_message). Минимум 3 символа.
```

### `services/membership.py`

```python
async def is_group_member(bot, user_id, group_id) -> bool
    # Valid: MEMBER, ADMINISTRATOR, CREATOR, RESTRICTED
    # Invalid: LEFT, KICKED. Любая ошибка → False.

async def is_admin(bot, user_id, group_id) -> bool
    # True только для ADMINISTRATOR, CREATOR.
```

### `services/rate_limiter.py`

```python
class RateLimiter:
    def __init__(self, limit=10, window_seconds=3600): ...
    def check_limit(user_id) -> dict
        # {"allowed": bool, "remaining": int, "reset_in": int, "current": int}
    def record_submission(user_id) -> None

def get_rate_limiter() -> RateLimiter  # singleton, config.RATE_LIMIT
```

> **Алгоритм:** sliding window. На каждый `check_limit` устаревшие записи отфильтровываются. Окно 3600 сек по умолчанию.

### `services/publisher.py`

```python
def format_anonymous_message(content) -> str
    # "🔒 <b>Анонимный вопрос</b>\n\n{content.text}"

async def publish_question(bot, content, group_id, topic_id) -> int
    # Шлёт send_message/send_photo с message_thread_id=topic_id.
    # Возвращает message_id. ValueError при ошибке Telegram API.

async def delete_from_topic(bot, group_id, topic_id, message_id) -> bool
    # True если удалено. False если "message to delete not found".
    # ValueError при других ошибках.
```

### `database.py` — все функции

| Функция | Назначение |
|---------|------------|
| `init_db(db_path)` | Создать таблицы/индексы, вернуть connection |
| `ensure_user(...)` | Upsert пользователя (зарезервировано) |
| `get_user_questions(db, user_id, limit=5, hours=24)` | Для `/delete`: только `approved`, не удалённые |
| `delete_question(db, qid, user_id)` | Soft delete + вернуть topic info для удаления в группе |
| `get_group_config(db, group_id)` | topic_id для конкретной группы |
| `set_group_config(db, group_id, topic_id)` | Upsert конфига группы |
| `get_latest_group_config(db)` | Активная цель публикации (последний `/set_topic`) |
| `save_pending_question(...)` | Создать вопрос со статусом `pending` |
| `approve_question(db, qid, topic_message_id)` | `pending → approved`, записать message_id |
| `reject_question(db, qid)` | `pending → rejected` (только если был pending) |
| `get_user_id_by_question(db, qid)` | Для уведомления автора при reject |
| `get_question_by_id(db, qid)` | Полные данные вопроса (для approve) |
| `get_moderation_history(db, limit=20)` | Последние approved/rejected для `/mod_history` |
| `get_stats(db)` | `{total, approved, rejected, pending}` для `/stats` |

---

## ⚙️ Конфигурация

Все настройки — переменные окружения, загружаемые `pydantic-settings` из `.env`.

| Переменная | Обяз. | Тип | По умолч. | Описание |
|------------|:---:|-----|-----------|----------|
| `BOT_TOKEN` | ✅ | str | — | Токен от @BotFather (валидация: содержит `:`) |
| `GROUP_ID` | ✅ | int | — | ID группы (отрицательное для supergroup). Используется как fallback |
| `ADMIN_ID` | ✅ | int | — | Telegram user ID модератора |
| `RATE_LIMIT` | — | int | `10` | Вопросов в час на пользователя (1–100) |
| `LOG_LEVEL` | — | str | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` |
| `DB_PATH` | — | str | `data/bot.db` | Путь к SQLite файлу |

> **Важно:** `GROUP_ID` — это **fallback**. Активная группа+топик определяется записью в `group_configs` с самым свежим `updated_at` (команда `/set_topic`). Это позволяет переключать целевую группу без редактирования `.env`.

Шаблон конфигурации: [`.env.example`](.env.example).

---

## 🚀 Быстрый старт

### Предварительные требования

1. **Создать бота:** [@BotFather](https://t.me/BotFather) → `/newbot` → получить `BOT_TOKEN`.
2. **Отключить privacy mode** (чтобы бот читал сообщения в группе): @BotFather → `/setprivacy` → выбрать бота → `Disable`.
3. **Узнать свой user ID** (будет `ADMIN_ID`): написать [@userinfobot](https://t.me/userinfobot).
4. **Узнать ID группы**: добавить [@RawDataBot](https://t.me/RawDataBot) в группу, он покажет `chat.id` (отрицательное).

### Установка

```bash
git clone https://github.com/Bondartsov/telegram-anon-bot.git
cd telegram-anon-bot

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Отредактировать .env: вписать BOT_TOKEN, GROUP_ID, ADMIN_ID
```

### Запуск (разработка)

```bash
python -m src.main
```

### Первичная настройка в Telegram

1. Добавить бота в группу как **администратора** (иначе не сможет публиковать/удалять).
2. В группе создать топик (thread) для вопросов.
3. Зайти в этот топик, отправить `/set_topic` — бот запомнит цель.
4. Проверить: написать боту в ЛС тестовый вопрос → одобрить в чате с админом.

---

## 📦 Развёртывание

Поддерживаются три способа.

### Способ 1: systemd (рекомендуется для VM)

```bash
# Первый деплой (с машины разработчика)
./deploy.sh --first-run

# Обновление кода
./deploy.sh
```

`deploy.sh` делает: rsync кода → `pip install` в venv → (опц.) установка `.service` → `systemctl restart`.

`anon-bot.service` запускает `/home/user/telegram-anon-bot/venv/bin/python -m src.main` с `Restart=always`.

### Способ 2: Docker

```bash
docker build -t anon-bot .
docker run -d --name anon-bot --env-file .env -v $(pwd)/data:/app/data anon-bot
```

### Способ 3: docker-compose

```bash
docker-compose up -d
docker-compose logs -f
```

`docker-compose.yml` настраивает `restart: unless-stopped`, монтирует `./data` для персистентности SQLite и ограничивает размер логов (`max-size: 10m, max-file: 3`).

---

## 🛠 Эксплуатация и операции

### Управление сервисом (systemd)

```bash
systemctl status anon-bot          # статус
systemctl restart anon-bot         # перезапуск
systemctl stop anon-bot            # остановка
journalctl -u anon-bot -f          // логи в реальном времени
journalctl -u anon-bot -n 100      // последние 100 строк
```

### Полезные SQL-запросы к БД

```bash
sqlite3 data/bot.db
```

```sql
-- Активная цель публикации
SELECT group_id, topic_id, updated_at FROM group_configs ORDER BY updated_at DESC LIMIT 1;

-- Вопросы по статусам
SELECT status, COUNT(*) FROM questions GROUP BY STATUS;

-- Последние 10 вопросов с авторами (только для админа!)
SELECT created_at, status, user_id, substr(content,1,50) FROM questions ORDER BY created_at DESC LIMIT 10;

-- Очистить отклонённые старше 30 дней
DELETE FROM questions WHERE status='rejected' AND created_at < datetime('now','-30 days');
```

### Обновление бота

```bash
git pull origin main
pip install -r requirements.txt        # если зависимости изменились
sudo systemctl restart anon-bot
```

### Бэкап

Критичные для сохранения файлы:
- `data/bot.db` — вся история вопросов и конфиги групп
- `.env` — токен и ID

```bash
# Бэкап БД
cp data/bot.db "data/bot.db.$(date +%Y%m%d).bak"
```

### Откат кода

```bash
# Посмотреть историю
git log --oneline

# Откатиться к конкретному коммиту
git checkout <commit-hash> -- src/
sudo systemctl restart anon-bot
```

---

## ❓ Устранение неисправностей (FAQ)

### Бот не отвечает на сообщения

1. **Проверить статус процесса:** `systemctl status anon-bot` → `active`?
2. **Только один процесс!** `ps aux | grep src.main` — если два, убить лишний. Long polling не терпит конкуренции: два процесса вызовут Telegram flood control.
3. **Проверить лог:** `journalctl -u anon-bot -n 50` — есть ли `Bot started: @username` и `Starting polling...`?
4. **Проверить токен:** `curl -s "https://api.telegram.org/bot<TOKEN>/getMe"` → должно вернуть `{"ok":true,...}`.

### `Flood control exceeded on getUpdates` в логах

Признак **двух запущенных копий бота** или слишком частого переподключения. Решение: оставить ровно один процесс, дождаться снятия ограничения (~минуту).

### Вопросы не публикуются в группу

1. **Бот должен быть админом группы** — иначе `TelegramForbiddenError`.
2. **`/set_topic` должен быть вызван** — иначе `get_latest_group_config()` вернёт `None`, и вопрос не примется вообще.
3. **Топик должен существовать** — если топик удалили, публикация упадёт.

### `/delete` показывает «нет вопросов»

Нормально, если за последние 24 часа нет **одобренных** вопросов. В списке только `status='approved' AND is_deleted=0`.

### Как сменить целевую группу/топик

Просто вызвать `/set_topic` в новом топике. Запись в `group_configs` обновит `updated_at`, и новый target станет активным. Перезапуск не нужен.

### Как сменить администратора

Поменять `ADMIN_ID` в `.env` и `sudo systemctl restart anon-bot`. Старые inline-кнопки модерации от старого админа перестанут работать для нового.

### Rate limiter «сбросился»

Это ожидаемо: счётчик в памяти процесса. После рестарта все получают свежий лимит. Если нужна персистентность — потребуется перенос на Redis/БД (не реализовано).

### Логический уровень

| Уровень | Когда ставить |
|---------|---------------|
| `DEBUG` | Отладка: показывает SQL, попадания в rate limiter, membership-чеки |
| `INFO` (по умолч.) | Рабочий режим: ключевые события |
| `WARNING` | Только проблемы |
| `ERROR` | Только ошибки |

Ставится через `LOG_LEVEL=DEBUG` в `.env` + restart.

---

## 📁 Структура проекта

```
telegram-anon-bot/
├── src/
│   ├── main.py                  # Точка входа: Bot, Dispatcher, middleware, polling
│   ├── config.py                # BotConfig (pydantic-settings), setup_logging
│   ├── database.py              # SQLite schema + все CRUD-операции
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── private.py           # ЛС: /start, /delete, /mod_history, /stats, приём вопросов
│   │   ├── group.py             # Группа: /set_topic, /settings, /start
│   │   └── callback.py          # Inline-кнопки: модерация (approve/reject) + удаление
│   └── services/
│       ├── __init__.py
│       ├── anonymizer.py        # AnonContent, prepare_content, validate_content
│       ├── membership.py        # is_group_member, is_admin
│       ├── publisher.py         # publish_question, delete_from_topic
│       └── rate_limiter.py      # RateLimiter (sliding window, in-memory)
├── .env.example                 # Шаблон конфигурации
├── .gitignore                   # Исключения (.env, *.log, data/*.db, venv/)
├── requirements.txt             # Зависимости (core + dev)
├── Dockerfile                   # Образ: python:3.11-slim, non-root
├── docker-compose.yml           # Сервис с restart и volume для data/
├── deploy.sh                    # Авто-деплой на VM (--first-run для первичной установки)
├── anon-bot.service             # systemd unit
└── README.md                    # Этот файл
```

### Зависимости времени выполнения

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `aiogram` | ≥3.15 | Telegram Bot API framework (async) |
| `aiosqlite` | ≥0.20 | Асинхронный доступ к SQLite |
| `pydantic` | ≥2.0 | Валидация конфигурации |
| `pydantic-settings` | ≥2.0 | Загрузка настроек из `.env` |

Dev-зависимости (`ruff`, `black`, `pytest`, `pytest-asyncio`) указаны в `requirements.txt`, но не требуются для запуска.

---

## 📄 Лицензия

MIT. См. условия лицензии для деталей.

---

> 📌 **Поддержка README в актуальном состоянии:** этот файл отражает архитектуру и поведение кода на момент последнего коммита. При изменении команд, схем БД или потоков — обновляйте соответствующие разделы, особенно [Жизненный цикл вопроса](#-жизненный-цикл-вопроса), [Схему базы данных](#-схема-базы-данных) и [Команды](#-команды-и-взаимодействия).
