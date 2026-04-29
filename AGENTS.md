# MatchMe — контекст для ассистента / нового разработчика

Читай этот файл **в начале сессии**, чтобы быстро войти в курс дела. Детали деплоя и API — в **`README.md`**.

## Продукт в одном абзаце

**MatchMe** — веб-MVP для знакомств/дружбы **по ценностям и ответам на вопросы**, а не по фото. Пользователь проходит онбординг-тест (оси совместимости), получает матч-% с другими, лайки, личные чаты при взаимности, групповые комнаты по близости ответов, ленту постов в стиле Threads (`/timeline`).

## Стек

| Слой | Технологии |
|------|------------|
| Backend | Python **FastAPI**, SQLAlchemy, Alembic, JWT, bcrypt |
| DB | Локально чаще **SQLite** (`backend/matchme.db`); прод — **PostgreSQL** (`DATABASE_URL`) |
| Frontend | **Next.js 14** (App Router), **Tailwind**, шрифт **Geist** |
| Mobile | Опционально Capacitor Android в `mobile/matchme-android/` |

## Фронтенд: дизайн и код

- **Тема:** светлая (**белый** фон, тёмный текст). Акцент — **пастельный синий** через Tailwind **`sky-*`** (раньше была тёмная тема и **emerald** — в коде могут встретиться следы в комментариях/истории).
- **Дизайн-система:** классы **`mm-*`** в **`frontend/app/globals.css`** (`mm-page`, `mm-card`, `mm-btn-primary`, …). Тени **`shadow-mm-card`**, **`shadow-mm-nav`** в **`frontend/tailwind.config.ts`**.
- **Навигация:** **`frontend/components/BottomNav.tsx`** — фиксированная нижняя панель; опрос **`GET /conversations/unread-count`** для красного бейджа на «Чаты».
- **API-клиент:** **`frontend/lib/api.ts`** — JWT, прокси `/api`, **`avatarPublicSrc()`**, ретраи GET при 502/504.
- **Чаты:** **`frontend/app/chat/[id]/page.tsx`**, **`frontend/app/group-chat/[id]/page.tsx`** — поллинг через **`useChatPolling`** (`frontend/lib/hooks/useChatPolling.ts`). Скролл ленты сообщений: контейнер с **`flex-1 min-h-0 overflow-y-auto`** (без **`min-h-0`** flex-ребёнок не сжимается и скролл «ломается»).
- **Уведомления:** **`frontend/lib/chatClient.ts`** — `playSoftMessagePing`, `showChatNotificationIfAllowed`, `requestNotificationPermission`. **`frontend/components/GlobalChatAlerts.tsx`** в **`app/layout.tsx`** — на экранах **не** `/chat/*` и **не** `/group-chat/*` опрашивает счётчик непрочитанных и при росте и скрытой вкладке даёт звук + системное уведомление.

## Бэкенд: куда смотреть

- **`backend/app/main.py`** — приложение FastAPI.
- **`backend/app/core/matching.py`** — матчинг по осям, батчи для ленты.
- **`backend/app/api/routes/`** — роутеры (чат, лента, треды, пользователи).
- **`backend/app/config.py`** — пороги групп **`group_*`**, JWT, CORS.
- Сиды: **`backend/seed.py`**, фикстуры: **`backend/scripts/seed_fixture_users.py`**.

## Документация (человеческая)

| Файл | Содержание |
|------|------------|
| `README.md` | Запуск, Render, Neon, состояние MVP, производительность |
| `CONCEPT.md` | Концепция продукта |
| `PRODUCT_VISION.md` | Продуктовое видение |
| `MVP_FLOW.md` | Экраны и сценарии MVP |
| `TODO.md` | Чеклист и фазы |

## Соглашения в этом репозитории

- После осмысленных изменений в коде — **коммит и push в `main`** (если пользователь не просит иначе).
- Не раздувать PR без запроса; правки **по задаче**.

## Ограничения MVP (кратко)

Нет OAuth в проде-качестве; тексты **terms/privacy** — черновики; push «как в Telegram» при **полностью** закрытом приложении потребует **Web Push** + service worker (сейчас — браузерные Notification + звук при активной сессии/вкладке в фоне).
