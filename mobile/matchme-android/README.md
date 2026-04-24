# MatchMe для Android (Capacitor)

Оболочка: нативное Android-приложение с **WebView**, которое грузит ваш **опубликованный** сайт (Next.js на Render / другом хосте). Запросы к API идут так же, как в браузере: через `https://ваш-фронт/.../api/...` (редирект Next на бэкенд), если вы **не** задавали `NEXT_PUBLIC_API_URL` и прокси на фронте настроен.

## Требования

- **Node.js 20+**
- **Android Studio** (SDK, эмулятор или устройство с USB-отладкой)
- **JDK 17** (часто идёт в составе Android Studio)

## 1. URL фронта

Перед `cap sync` задайте переменную **`MATCHME_WEB_URL`** — полный `https://...` до вашего Next **без** хвостового `/`, например:

`https://matchme-frontend.onrender.com`

Локальная сеть (эмулятор к хосту): часто `http://10.0.2.2:3000` (HTTP). Для cleartext см. `capacitor.config.ts` (`cleartext: true` при `http://`).

## 2. Установка и первичная инициализация

```powershell
cd mobile\matchme-android
npm install
```

Если папки **`android/`** ещё нет в репозитории (первый раз на машине):

```powershell
npx cap add android
```

## 3. Синхронизация с URL (каждый раз после смены `MATCHME_WEB_URL`)

**PowerShell:**

```powershell
$env:MATCHME_WEB_URL="https://ваш-фронт.onrender.com"
npx cap sync android
```

**cmd:**

```cmd
set MATCHME_WEB_URL=https://ваш-фронт.onrender.com
npx cap sync android
```

## 4. Запуск в Android Studio

```powershell
npx cap open android
```

Дальше: **Run** на эмуляторе или устройстве. Первый билд может занять несколько минут (Gradle).

## 5. Пакет и подпись (Google Play)

- **Application ID** сейчас: **`com.matchme.app`**. Смена после публикации нежелательна — поменяйте в `capacitor.config.ts` *до* `npx cap add android`, либо правьте `applicationId` в Gradle и пересоберите.
- Релизный **AAB** собирается в Android Studio: **Build → Generate Signed Bundle / APK** (keystore храните отдельно, не в git).

## 6. CORS и API

- Если фронт открывается по **тому же origin**, что и запросы к `/api/...` — как в обычном браузере, дополнительных настроек CORS для мобильного WebView обычно **не** нужно.
- Если в проде задан **`NEXT_PUBLIC_API_URL`** с прямым URL бэкенда — в **`CORS_ORIGINS`** бэкенда (Render) должен быть **origin вашего фронта** (или `capacitor://` / custom scheme в зависимости от схемы; для удалённого `server.url` origin страницы = URL фронта).

## 7. PWA / TWA

Альтернатива магазину приложений: **PWA** или **TWA (Trusted Web Activity)** — отдельная тема; Capacher даёт полноценный APK и больше контроля над иконкой и публикацией в Play.

## Траблшутинг

- **Пустой экран / ERR_CLEARTEXT:** для `http://` на эмуляторе нужен `cleartext: true` (уже привязан к `http` в `capacitor.config.ts`). Для HTTPS — проверьте сертификат и URL.
- **Старый кэш WebView:** в настройках приложения «Очистить данные» или переустановка.
- **502 на Render:** то же, что в браузере (cold start); автоповторы на фронте остаются актуальны.
