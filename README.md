<div align="center">

# 🚀 ZenitarParser Pro

### Профессиональный софт для парсинга, инвайтинга и рассылки в Telegram

**Парсер · Инвайтер · Рассыльщик · Управление аккаунтами · Прокси · Антибан**

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![aiogram](https://img.shields.io/badge/aiogram-3.10-2CA5E0?logo=telegram&logoColor=white)
![Pyrogram](https://img.shields.io/badge/Pyrogram-2.0-red)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

*Полностью управляется через Telegram-бота. Без копания в коде — всё в кнопках.*

</div>

---

## ✨ Возможности

<table>
<tr>
<td width="50%" valign="top">

### 🔍 Парсер
- 👥 Участники группы: все / активные / админы / боты
- ✍️ Активные пользователи (по истории сообщений)
- 🔎 Поиск чатов по ключевым словам
- ❤️ Те, кто поставил реакцию на пост
- 💬 Комментаторы поста канала
- 📂 История экспортов прямо в боте

### 🎯 Аудитория
- 🧹 Дедупликация (по id / username)
- ➕ Объединение нескольких списков
- ➖ Вычитание (исключить уже приглашённых)
- 🔬 Фильтры: @username / Premium / без ботов / только люди

</td>
<td width="50%" valign="top">

### 📨 Инвайтер
- Массовый инвайт из CSV в группу
- 🔄 Ротация по всем аккаунтам
- 🛡 Автокулдаун при флуде, дневные лимиты

### 📢 Рассыльщик
- 👤 Через юзербот (Pyrogram) — ротация по пулу
- 🤖 Через ботов (Bot API) — быстро, ротация
- 🧩 Шаблоны: `{name}` `{username}` `{full_name}`
- 👀 Превью и 🧪 тест-отправка перед запуском

### 🛠 Профильные инструменты
- ✏️ Имя · 📝 Bio · 🔗 Username · 🖼 Аватар
- ➕➖ Вступление / выход из чатов
- 🌐 Смена прокси «на лету»
- 🛡 Проверка спам-блока через @SpamBot

</td>
</tr>
</table>

### 🏗 Production-готовность
`🔄 Мульти-аккаунт` `🌐 SOCKS5/HTTP прокси` `🛡 Антибан-лимиты` `📊 Статистика` `📝 Логи с ротацией` `🐳 Docker` `♻️ Graceful shutdown` `🔒 Только для админов` `🗄 SQLite` `⚡ Опциональный Redis FSM`

---

## ⚡ Быстрый старт

### 🐳 Docker (рекомендуется)

```bash
git clone https://github.com/SyberianIT/ZenitarParser_bot-Python-Telegram.git
cd ZenitarParser_bot-Python-Telegram/ZenitarParser

cp .env.example .env      # заполните API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS
docker compose up -d --build
docker compose logs -f bot
```

### 🐍 Локально

```bash
cd ZenitarParser_bot-Python-Telegram/ZenitarParser
./setup.sh                # venv + зависимости + .env
nano .env                 # заполните данные
source venv/bin/activate
python main.py
```

---

## ⚙️ Конфигурация (`.env`)

```ini
# Telegram API — https://my.telegram.org → API development tools
API_ID=12345
API_HASH=ваш_api_hash

# Бот — @BotFather
BOT_TOKEN=ваш_токен

# Админы — @userinfobot (несколько через запятую)
ADMIN_IDS=123456789

# Антибан-лимиты на аккаунт в сутки
MAX_INVITES_PER_DAY=40
MAX_MESSAGES_PER_DAY=30
FLOOD_COOLDOWN=3600

# Задержки между действиями, "мин-макс" сек
DEFAULT_DELAY_INVITE=20-45
DEFAULT_DELAY_SEND=15-40

# Опционально: персистентный FSM
# REDIS_URL=redis://redis:6379/0
LOG_LEVEL=INFO
```

| Параметр | Где взять |
|----------|-----------|
| `API_ID`, `API_HASH` | [my.telegram.org](https://my.telegram.org) → API development tools |
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | [@userinfobot](https://t.me/userinfobot) |

---

## 📖 Как пользоваться

```
1️⃣  /start  →  открыть панель управления (живой дашборд)
2️⃣  👥 Аккаунты → ➕ Добавить  →  прокси → телефон → код → 2FA
3️⃣  🔍 Парсер  →  собрать аудиторию → получить CSV
4️⃣  🎯 Аудитория  →  почистить/объединить/исключить/отфильтровать
5️⃣  📨 Инвайтер  →  загрузить CSV → указать группу
6️⃣  📢 Рассыльщик  →  CSV → текст → превью → 🚀 запуск
```

> 💡 **Чем больше аккаунтов — тем выше суммарные лимиты и устойчивость к флуду.**
> Работа автоматически распределяется по всем активным аккаунтам с ротацией.

Команды бота: `/menu` · `/cancel` · `/help`

---

## 🗂 Архитектура

```
ZenitarParser/
├── main.py                  # точка входа, DI, graceful shutdown
├── config.py                # конфиг из .env + валидация
├── database.py              # SQLite: настройки, аккаунты, лимиты, статистика
├── .env.example · Dockerfile · docker-compose.yml · setup.sh
│
├── modules/                 # бизнес-логика (без Telegram UI)
│   ├── session_manager.py   #   мульти-аккаунт + прокси + reconnect
│   ├── account_pool.py      #   ротация, лимиты, кулдауны (антибан)
│   ├── parser.py            #   участники/активные/ключи/реакции/комменты
│   ├── audience.py          #   операции над списками (чистая логика)
│   ├── inviter.py           #   инвайт с ротацией
│   ├── sender.py            #   рассылка (юзербот + Bot API)
│   └── profile.py           #   имя/bio/username/аватар/join/spam-check
│
├── handlers/                # Telegram UI (aiogram 3 + FSM)
│   ├── start.py             #   дашборд-панель, /menu /help /cancel
│   ├── parser.py · audience.py · inviter.py · sender.py
│   └── accounts.py · profile.py · settings.py
│
└── utils/
    ├── keyboards.py · export.py · tasks.py · logger.py · identity.py
```

**Принцип:** `modules/` — переиспользуемая логика без привязки к Telegram, `handlers/` — только UI и FSM. Легко тестировать и расширять.

---

## 🛡 Антибан-механика

- **Дневные лимиты** на каждый аккаунт (`MAX_INVITES_PER_DAY`, `MAX_MESSAGES_PER_DAY`)
- **Автокулдаун** при `PeerFlood` / `FloodWait` — аккаунт временно исключается из ротации
- **Ротация** работы по всему пулу — нагрузка размазывается
- **Случайные задержки** между действиями (настраиваемые)
- **Индивидуальные прокси** на аккаунт
- **Статусы аккаунтов** в панели: ✅ активен · 🌊 кулдаун · 🚫 бан · ❌ отключён

---

## ❓ FAQ

<details>
<summary><b>Бот пишет «Нет доступа»</b></summary>

Ваш Telegram ID не в `ADMIN_IDS`. Узнайте ID у [@userinfobot](https://t.me/userinfobot) и впишите в `.env`.
</details>

<details>
<summary><b>«Нет доступных аккаунтов»</b></summary>

Добавьте аккаунт в 👥 *Аккаунты* → *Добавить*, либо все аккаунты на кулдауне/исчерпали дневной лимит — подождите или поднимите лимиты в `.env`.
</details>

<details>
<summary><b>Инвайт не добавляет людей</b></summary>

Аккаунт должен состоять в целевой группе и иметь право добавлять участников. У многих юзеров приватность запрещает инвайт — это нормально (счётчик «Приватность»).
</details>

<details>
<summary><b>Где взять .session аккаунтов?</b></summary>

Не нужно вручную. Добавляйте аккаунты прямо в боте по номеру телефона — он сам создаст сессию (с поддержкой 2FA).
</details>

---

## ⚠️ Дисклеймер

Инструмент предназначен для **законного маркетинга** и работы с собственной аудиторией. Соблюдайте [Условия использования Telegram](https://telegram.org/tos) и законодательство о персональных данных и рекламе. Агрессивные настройки приводят к блокировке аккаунтов — используйте разумные лимиты и задержки. Вся ответственность за использование лежит на пользователе.

---

<div align="center">

**Автор:** SyberianIT  ·  **Лицензия:** MIT

⭐ Поставьте звезду, если проект полезен

</div>
