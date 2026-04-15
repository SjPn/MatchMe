# MatchMe

Веб-MVP: **FastAPI** (backend) и **Next.js** (frontend).

**Локально по умолчанию — SQLite** (файл `matchme.db` в каталоге `backend/`). Путь к `sqlite:///./matchme.db` в приложении **резолвится в абсолютный** под `backend/`, чтобы не плодить разные файлы БД при разном `cwd`. **На проде** — `DATABASE_URL` на **PostgreSQL**; те же модели, Alembic и `psycopg2` в зависимостях.

## Состояние MVP (снимок)

| Слой | Сделано |
|------|---------|
| **Данные** | Пользователи, вопросы (`pack=onboarding`), оси (`question_axes`), связи вопрос–ось, ответы, лайки; **личные** чаты (матч → `conversations`/`messages`); **групповые** комнаты (`group_rooms`, участники, сообщения, жалобы) |
| **Матчинг v0** | Счёт по осям из ответов через `question_axis_link`; сравнение только по осям, где **у обоих** есть реальный счёт; `%` = среднее `(1 − \|Δ\|)` по таким осям. Группы: пороги среднего/макс. расхождения по осям и мин. размер когорты — `app/config.py` (`group_*`) |
| **API** | Регистрация/логин JWT, вопросы, ответы, лента, сравнение, лайки, личный чат (`/conversations`), групповой чат (`/group-rooms`), **Threads-like коммуникации** (`thread_posts`): `/timeline`, `/posts/{id}`, `/posts/{id}/replies`, `/posts`, `/posts/{id}/reply`, `/posts/{id}/can-reply`, лайки/репост/цитата для постов; **темы** как фильтр `/timeline?topic=...` + `/axes`; **активность пользователя** (`GET /users/{id}/threads?kind=posts|replies`); **аватары** (`POST/DELETE /me/avatar`, `GET /users/{id}/avatar`); **блокировка и жалоба на пользователя** (`POST/DELETE /users/{id}/block`, `POST /users/{id}/report`), `PATCH /me/profile` |
| **UI** | Тёмная тема, **дизайн-система `mm-*`** (классы в `app/globals.css`), шрифт **Geist**, нижняя навигация; онбординг, тест, summary, **`/terms` и `/privacy`**, регистрация с галочкой согласия, **Threads-like лента** (`/timeline`) с вкладкой «Темы» (чипсы осей), детали поста (`/posts/[id]`), экран ветки (`/threads/[id]`), composer bottom-sheet; профили (`/users/[id]`) с «как думает» в chips, аккордеоном деталей и активностью (посты/комментарии); диалоги (**личные + группы**), `/chat/[id]` и `/group-chat/[id]` |
| **Демо** | `python seed.py` — вопросы; `python scripts/seed_fixture_users.py` — симуляция (**100** пользователей по умолчанию, **случайные** ответы; пароль у всех один — `ChaosDemo2026!`, см. константу в скрипте; `--count`, `--domain`) |

**Ограничения:** OAuth нет; тексты `/terms` и `/privacy` — **черновики** (нужна юридическая проверка перед публичным запуском); лента не ранжирует ML — сортировка по `%` среди всех пользователей.

**Производительность (актуально для Neon):** тяжёлые пути матчинга переведены на **батч-загрузку ответов** (`compute_user_axis_scores_batch` в `core/matching.py`): лента (`GET /feed`), подбор группы (`core/group_matching.py`), блок «общее в комнате» (`core/group_traits.py`). **Списки тредов** (`GET /timeline`, детали поста, ответы, **`GET /users/{id}/threads`**) собираются через **`_build_posts_out`** в `thread_posts.py` — один проход по постам с батчем авторов, медиа, счётчиков и тем, без N+1. На фронте независимые запросы при открытии чата, группы и ленты людей выполняются **параллельно** (`Promise.all`); список осей для вкладки **«Темы»** в `/timeline` подгружается **лениво** (только при переключении на вкладку). Для **GET** при **502/503/504** и сетевых сбоях в `frontend/lib/api.ts` включены **автоповторы** (удобно при cold start на Render). Подробнее — раздел **«Производительность и задержки»** ниже.

**Блокировки (1:1):** если пользователь A заблокировал B (или наоборот), они **не видят** друг друга в ленте, не могут сравнение/лайк/личный чат; записи в `user_blocks` / `user_reports`. **Групповые** жалобы остаются в `group_message_reports`.

Подробнее: `CONCEPT.md`, `MVP_FLOW.md`, `TODO.md`.

## Конкуренты (быстрый ориентир)

См. `CONCEPT.md` → раздел **«Конкуренты и похожие решения (2026)»**. Коротко: массовые (Bumble BFF), вопросники (OkCupid), платонические friend‑apps (Patook/We3‑подобные), сообщества/группы (Meetup/Geneva), асинхронные форматы (Slowly). Наша ставка в MVP — **объяснимые оси** + **групповые комнаты** для снижения барьера общения.

## Требования

- Python 3.11+
- Node.js 20+
- PostgreSQL (Neon) — если в `backend/.env` задан `DATABASE_URL` на Neon; иначе по умолчанию можно работать на **SQLite** локально

## 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Пароли хэшируются через пакет **`bcrypt`** (без `passlib`, чтобы не ломаться на новых версиях bcrypt). После обновления кода всегда повторяй `pip install -r requirements.txt`.

В `.env` для разработки: либо строка **Neon** из консоли (см. комментарии в `backend/.env`), либо без Neon — `DATABASE_URL=sqlite:///./matchme.db`.

Запускать **из каталога `backend`** (иначе пакет `app` не импортируется). Дальше:

```powershell
$env:PYTHONPATH = "."
alembic upgrade head
python seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Или **`serve.bat`** / **`serve.ps1`** в корне `backend` — они делают `cd` в эту папку и запускают uvicorn.

**Демо-пользователи** (после `seed.py`): `chaos001@matchme.demo` … `chaos100@matchme.demo`, пароль **`ChaosDemo2026!`** (или что задано в `CHAOS_PASSWORD` в скрипте). Повторный запуск **перезаписывает** ответы и пароли у этих же email.

```powershell
python scripts/seed_fixture_users.py
python scripts/seed_fixture_users.py --count 20
```

**Диагностика групповых комнат** (сколько совместимых пар при текущих порогах, сколько комнат в БД):

```powershell
python scripts/diagnose_group_cohorts.py
```

Пороги `group_*` задаются в `app/config.py` или через переменные окружения (см. `.env.example`). После сида со **случайными** ответами комнаты могут не создаваться — ослабьте пороги или добавьте пользователей с близкими ответами.

Миграции: репозиторий содержит цепочку Alembic (в т.ч. групповые таблицы `0007`). Выполняй **`alembic upgrade head`** перед продом и после `git pull`. Ревизия **`0001`** создаёт начальную схему через **`Base.metadata.create_all()`** по **текущим** моделям, поэтому на пустой БД часть таблиц (в т.ч. `thread_posts`) может появиться уже на шаге `0001`; последующие ревизии, дублирующие DDL, сделаны **идемпотентными** (например `0013` не падает с `DuplicateTable`). На **SQLite** при старте API дополнительно подтягиваются недостающие колонки/таблицы (`app/database.py` + `lifespan`), но **вопросы** всё равно нужно залить через `python seed.py`. На **PostgreSQL** без миграций не обойтись.

- Swagger: http://127.0.0.1:8000/docs  
- Файл БД: `backend/matchme.db` (появится после миграций)

**Переход на PostgreSQL** (деплой): в `.env` или в переменных окружения сервера задай `DATABASE_URL`. Подойдёт и строка из Neon в виде `postgresql://USER:PASSWORD@HOST/DB?sslmode=require` — приложение само приведёт её к `postgresql+psycopg2://…` для SQLAlchemy.

```text
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/matchme
```

Создай пустую БД на сервере (в Neon база уже есть), затем **на сервере** после выставления переменных: `alembic upgrade head` и при необходимости `python seed.py`. Локальный `matchme.db` для этого не используется.

### Безопасность перед публикацией в GitHub

- **Не коммитить:** `backend/.env`, `frontend/.env.local`, файлы БД (`matchme.db`), загрузки (`backend/uploads/`). В корне уже учтено в `.gitignore`; перед первым `git push` выполни `git status` и убедись, что секретов в индексе нет.
- **Секреты в проде:** длинный случайный `JWT_SECRET`, свой `DATABASE_URL` только в переменных окружения Render (или другого хостинга), не в репозитории.
- Если строка подключения к БД или пароль **где-либо засветились** (чат, скриншот) — в панели Neon сразу **сбрось пароль / пользователя** и обнови переменные на Render.

### Neon + Render.com (черновик)

1. **Neon:** создать проект, скопировать connection string с `sslmode=require`. Хост с `-pooler` — для serverless/многих коротких соединений; приложение использует небольшой пул (см. `app/database.py`).
2. **Render (web service, Python):** корень сервиса — каталог `backend`; build: `pip install -r requirements.txt`; start:  
   `sh -c "export PYTHONPATH=. && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"`  
   **Обязательно зафиксировать Python ≤3.13** (например **`PYTHON_VERSION=3.12.11`** в **Environment** или файл **`backend/.python-version`** с той же строкой — при `rootDir: backend` это корень сборки). Иначе Render по умолчанию берёт **Python 3.14**, у `pydantic-core` из `requirements.txt` нет готового wheel под эту версию, pip пытается **собрать из исходников** (Rust/maturin) и падает с **`Read-only file system`** / **`metadata-generation-failed`**. В **`render.yaml`** уже задан `PYTHON_VERSION` для Blueprint.  
   Также задать: `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS` (URL фронта на Render).
3. **Фронт на Render (static или Next):** в `frontend` задать `BACKEND_URL` / `NEXT_PUBLIC_API_URL` под публичный URL API (см. `frontend/.env.local.example` и `next.config.mjs`).  
   **502 Bad Gateway на `/login`, `/feed` и др.:** запросы идут в Next (`/api/...`), Next проксирует на `BACKEND_URL`. Если сервис API **ещё «спит»** (бесплатный план) или **не успел ответить**, прокси отдаёт **502** с **HTML** (часто `<title>502</title>`) — это **не** traceback Python: в логах uvicorn при этом может не быть вашего кода. Если же в логах API виден **`500`** и **traceback** (например `ImportError`) — это **ошибка приложения**; после исправления и деплоя перезапустите сервис. Решения для 502: подождать и обновить страницу; **cron/ping** на `GET /health`; **always on**; проверить **`BACKEND_URL`** у фронта (HTTPS URL сервиса API). Автоповторы GET — см. `frontend/lib/api.ts`.

В репозитории есть пример **`render.yaml`** (без секретов) — можно подключить как Blueprint и дополнить переменными в UI Render.

## 2. Frontend

```powershell
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

http://localhost:3000 · API по умолчанию http://127.0.0.1:8000

**Пустая лента после перехода на PostgreSQL:** чаще всего браузер ходит **не в тот** процесс uvicorn (другой порт, старый SQLite). Оставьте **`NEXT_PUBLIC_API_URL` пустым** в `.env.local`, чтобы запросы шли на `/api` и проксировались через Next (`BACKEND_URL` → тот же бэкенд, что с `DATABASE_URL`). Если задаёте прямой URL API — это должен быть **тот же** uvicorn, что читает `backend/.env`. В ответе **`GET /auth/me`** есть поле `server_db_kind` (`sqlite` / `postgresql`); **`GET /feed/meta`** показывает, сколько других пользователей видит API в этой БД. Лента **не фильтрует** «только похожих» — в выборку попадают все остальные пользователи в этой БД (кроме блокировок и текстового поиска по «о себе»).

После входа пользователи с **уже пройденным** онбордингом (`onboarding_step=test_completed`) попадают в **ленту** (`/feed`), а не в тест заново. Прямой заход на `/test` при завершённом тесте перенаправляет на ленту.

**Дизайн и вёрстка:** переиспользуемые классы **`mm-page`**, **`mm-input`**, **`mm-btn-primary`** и др. в `frontend/app/globals.css`; ширина колонки **`max-w-shell`** / на больших экранах **`lg:max-w-shell-wide`** (см. `tailwind.config.ts`). Корневой `layout` подключает **Geist** (`app/fonts/`).

**Коммуникации (Threads-like):** единая сущность `thread_posts` (корневые посты + ответы = граф). Лента `/timeline` поддерживает фильтр по темам (оси) и ETag-поллинг. Правило «кто может отвечать» задаётся контрактом `value_policy_json` и проверяется через `/posts/{id}/can-reply` (возвращает `reason`, почему нельзя).

**Чаты:** в **личном** чате сообщения и список диалогов подгружаются **опросом** (порядка 2–5 с). В **группе** — отдельный экран `/group-chat/[id]` (текст, реплаи, жалоба, выход, «тихий режим»-флаг; лимит сообщений на стороне API). При первом открытии чата/группы фронт запрашивает **`/auth/me`**, детали и сообщения **параллельно** (где возможно), чтобы сократить «водопады» запросов. В личный чат можно отправлять **файлы** (multipart, до ~10 МБ); каталог `backend/uploads/chat/` не коммитится.

**Производительность и задержки**

- **Neon и сеть:** база в облаке (часто `us-east-1`) — каждый HTTP-запрос к API добавляет **десятки–сотни миллисекунд** только на TLS и RTT. Используйте connection string с **pooler** (`-pooler` в хосте), как в консоли Neon — в `app/database.py` уже настроен небольшой пул SQLAlchemy.
- **Бэкенд:** для ленты и групп не пересчитываются осевые профили **по отдельности на каждого пользователя в цикле** — один батч ответов на всех нужных `user_id`, затем сравнение в памяти (`compute_user_axis_scores_batch`, `axis_pair_rows_from_scores`, аналогично для группового матчинга и `group_shared_traits_for_user`). Списки постов тредов — **`_build_posts_out`** в `app/api/routes/thread_posts.py` (в т.ч. профиль **`/users/{id}/threads`** использует тот же хелпер, что и лента).
- **Фронт:** на страницах ленты людей первая загрузка объединяет **`/likes/inbox`**, **`/me/feed-preferences`** и **`/feed`**; на `/chat/[id]` и `/group-chat/[id]` — параллельно **`/auth/me`** и данные чата/комнаты. **`next dev`** компилирует страницы при первом заходе — переходы могут занимать **несколько секунд**; оценка «боевой» скорости: `npm run build` и `npm run start`. На проде при кратковременных **502** у прокси клиент **повторяет GET** с паузами (см. `lib/api.ts`).
- **Uvicorn `--reload`:** при сохранении файлов сервер перезапускается; незавершённые запросы обрываются (**CancelledError**, в логах может быть **500** / `socket hang up` у Next — это не обязательно баг приложения). Для стабильного теста без перезапусков запускайте API **без** `--reload`.

**Если `npm run build` падает** с ошибкой вроде `Cannot find module ... _document` или пропавших чанков — удалите кэш сборки и соберите снова: `Remove-Item -Recurse -Force .next` в каталоге `frontend/`.

## Структура

| Путь | Назначение |
|------|------------|
| `backend/app/` | FastAPI, модели, `core/matching.py` (в т.ч. батч осевых скоров), `core/group_matching.py`, `core/group_traits.py`, роутеры |
| `backend/app/api/routes/thread_posts.py` | Таймлайн/посты/ответы/лайки; **`_build_posts_out`** — единая батч-сборка `ThreadPostOut` без N+1 |
| `frontend/lib/api.ts` | `apiUrl`, JWT, **повторы GET** при 502/503/504 и сетевых ошибках; `apiJsonWithEtag` для поллинга |
| `backend/app/database.py` | `create_db_engine()` (пул для PostgreSQL), на SQLite при старте — совместимость схемы (колонки, групповые таблицы); `get_db` закрывает сессию без шума при остановке |
| `backend/app/config.py` | SQLite путь, JWT, CORS, лимиты загрузки и **пороги групповых комнат** (`group_*`) |
| `backend/alembic` | Миграции; первая поднимает схему, дальше — добавление таблиц/колонок (личный и групповой чат) |
| `backend/scripts/seed_fixture_users.py` | Симуляция N пользователей со случайными ответами |
| `backend/scripts/diagnose_group_cohorts.py` | Статистика совместимости и групповых комнат |
| `frontend/app/terms`, `privacy` | Условия и конфиденциальность (черновики) |
| `frontend/app/globals.css` | Tailwind-слои, классы **`mm-*`**, фон и токены UI |
| `frontend/tailwind.config.ts` | Шрифты, тени, **`shell` / `shell-wide`** |
| `frontend/components/BottomNav.tsx` | Нижняя навигация (иконки, активный маршрут) |
| `frontend/app/` | Остальные страницы Next.js App Router |
| `CONCEPT.md`, `MVP_FLOW.md`, `TODO.md` | Продукт, экраны, чеклист |
| `render.yaml` | Черновик сервиса API для Render.com (переменные — только в Dashboard) |

## Дальше

1. **Рост/трекшен:** выбрать нишу (город/язык/комьюнити), сделать приглашения/шары ссылок на треды и профили, базовые метрики (см. `TODO.md`).  
2. **Коммуникации:** уведомления (SSE/polling), контекст для ответов «в ответ на…», модерация тредов (скрыть/удалить), поиск/теги тем.  
3. **Профиль:** `next/image` для аватаров, редактирование display_name/о себе, приватность и индикаторы доверия (verification остаётся отдельным).  
4. **Запуск:** staging/прод, HTTPS, бэкапы БД, мониторинг.  
5. **После MVP:** OAuth, PWA/push, второй пак вопросов и ветвления.

### Идеи на будущее (по вашим пунктам)

1. **Коммуникации (углубление после Threads-like ядра):** подписки/фолловинг, push/уведомления, шаринг ссылок на треды, модерация постов — при сохранении псевдонимов и value-gating.
2. **Хостинг быстрее и “чище” по неймингу:** подобрать лучшее место деплоя, где можно получить короткие домены/без лишних слов в URL и где латентность будет ниже (регион ближе к пользователям, быстрый cold-start, нормальная работа с Postgres/пулом). Цель — заметно ускорить переходы (особенно первые запросы) по сравнению с текущим сетапом.

Подробный чеклист: **`TODO.md`**.
