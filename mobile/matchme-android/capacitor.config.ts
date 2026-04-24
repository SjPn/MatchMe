import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Укажи публичный URL Next.js (Render / Vercel / свой домен), без хвостового /.
 * Запуск: в PowerShell перед sync:
 *   $env:MATCHME_WEB_URL="https://matchme-frontend.onrender.com"; npx cap sync android
 *
 * Если переменная не задана — WebView откроет локальную заглушку из www/ (см. www/index.html).
 */
const webUrl = (process.env.MATCHME_WEB_URL || "").replace(/\/$/, "").trim() || undefined;

const isHttp = webUrl?.startsWith("http://") ?? false;

const config: CapacitorConfig = {
  appId: "com.matchme.app",
  appName: "MatchMe",
  webDir: "www",
  server: webUrl
    ? {
        url: webUrl,
        androidScheme: isHttp ? "http" : "https",
        cleartext: isHttp,
      }
    : undefined,
  android: {
    allowMixedContent: false,
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 0,
    },
  },
};

export default config;
