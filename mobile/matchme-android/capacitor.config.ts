import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Прод по умолчанию: фронт на Render. Переопределение: `MATCHME_WEB_URL` (пустая строка = только www/ без remote).
 */
const PROD_FRONTEND = "https://matchme-fo7z.onrender.com";

const explicit = process.env.MATCHME_WEB_URL;
const webUrl =
  explicit === ""
    ? undefined
    : (explicit ?? PROD_FRONTEND).replace(/\/$/, "").trim() || undefined;

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
