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
          "0 0 0 1px rgba(228, 228, 231, 0.9) inset, 0 8px 32px -12px rgba(15, 23, 42, 0.08)",
        "mm-nav": "0 -8px 32px -8px rgba(15, 23, 42, 0.06)",
      },
      transitionDuration: {
        DEFAULT: "180ms",
      },
    },
  },
  plugins: [],
};
export default config;
