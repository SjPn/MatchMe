import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
      },
      maxWidth: {
        /** Узкая колонка (телефон и по умолчанию) — как раньше max-w-lg */
        shell: "32rem",
        /** Широкий экран: ближе к центральной колонке ленты Threads (~680px) */
        "shell-wide": "680px",
      },
      boxShadow: {
        "mm-card":
          "0 0 0 1px rgba(255,255,255,0.04) inset, 0 8px 32px -12px rgba(0,0,0,0.55)",
        "mm-nav": "0 -8px 32px -8px rgba(0,0,0,0.45)",
      },
      transitionDuration: {
        DEFAULT: "180ms",
      },
    },
  },
  plugins: [],
};
export default config;
