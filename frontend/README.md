# MatchMe — frontend (Next.js)

Клиентское приложение монорепозитория **MatchMe**. Не используй этот файл как общий гайд по продукту — см. **`../README.md`** и **`../AGENTS.md`**.

## Стек

- **Next.js 14** (App Router), **React**, **Tailwind CSS**
- Шрифт **Geist** (`app/fonts/`)
- Запросы к API: через **`lib/api.ts`** (JWT в `localStorage`, при необходимости прокси **`/api/*`** → бэкенд из `next.config.mjs`)

## Тема и стили

- **Светлая** палитра: белый фон, текст `zinc-900` / `zinc-600`.
- Акцент — **синий** (**`sky-*`** в классах), токены в **`app/globals.css`** (`--mm-accent`, `--mm-accent-dim`, …).
- Переиспользуемые классы префикса **`mm-*`** (`mm-page`, `mm-card`, `mm-btn-primary`, …) задаются в **`app/globals.css`**.
- Ширина колонки: **`max-w-shell`** / на широких экранах **`lg:max-w-shell-wide`** — см. **`tailwind.config.ts`**.

## Запуск

```powershell
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Открыть [http://localhost:3000](http://localhost:3000). API по умолчанию — через прокси на тот же хост или **`NEXT_PUBLIC_API_URL`** (см. `.env.local.example`).

## Сборка

```powershell
npm run build
npm run start
```

На **Render** и других CI важно проходить **`npm run build`** (проверка TypeScript и ESLint в процессе Next).

## Важные пути в коде

| Путь | Назначение |
|------|------------|
| `app/layout.tsx` | Корневой layout, **`GlobalChatAlerts`** |
| `app/globals.css` | Tailwind + классы **`mm-*`**, фон body |
| `lib/api.ts` | HTTP-обёртка, **`avatarPublicSrc`**, ретраи |
| `lib/chatClient.ts` | Скролл «у низа», звук, Notification |
| `lib/hooks/useChatPolling.ts` | Поллинг сообщений в чатах |
| `components/BottomNav.tsx` | Нижнее меню и бейдж непрочитанных |
| `components/GlobalChatAlerts.tsx` | Уведомления при росте unread вне чата |

Подробнее о фичах и бэкенде — **`../README.md`**.
