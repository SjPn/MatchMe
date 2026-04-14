"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import { pathAfterAuth } from "@/lib/postAuthRedirect";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [acceptLegal, setAcceptLegal] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!acceptLegal) {
      setError("Нужно согласиться с условиями и политикой конфиденциальности.");
      return;
    }
    setLoading(true);
    try {
      const res = await api<{ access_token: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, display_name: displayName }),
      });
      setToken(res.access_token);
      const next = await pathAfterAuth();
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mm-page-auth">
      <div className="mm-card-static p-8 sm:p-10">
        <h1 className="mm-h1 text-center">Регистрация</h1>
        <p className="mm-lead text-center mt-3">Email и пароль (минимум 8 символов)</p>
        <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-5">
          <label className="mm-label">
            <span>Имя</span>
            <input
              className="mm-input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              autoComplete="name"
            />
          </label>
          <label className="mm-label">
            <span>Email</span>
            <input type="email" className="mm-input" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </label>
          <label className="mm-label">
            <span>Пароль</span>
            <input
              type="password"
              className="mm-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
              autoComplete="new-password"
            />
          </label>
          <label className="flex items-start gap-3 text-sm text-zinc-400 cursor-pointer">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 rounded border-zinc-600 bg-zinc-900 text-emerald-500 focus:ring-emerald-500/40"
              checked={acceptLegal}
              onChange={(e) => setAcceptLegal(e.target.checked)}
            />
            <span className="leading-snug">
              Соглашаюсь с{" "}
              <Link href="/terms" className="mm-link" target="_blank" rel="noopener noreferrer">
                условиями
              </Link>{" "}
              и{" "}
              <Link href="/privacy" className="mm-link" target="_blank" rel="noopener noreferrer">
                политикой конфиденциальности
              </Link>
              .
            </span>
          </label>
          {error ? <p className="mm-error whitespace-pre-wrap">{error}</p> : null}
          <button type="submit" disabled={loading || !acceptLegal} className="mm-btn-primary w-full py-3.5">
            {loading ? "Создаём…" : "Создать аккаунт"}
          </button>
        </form>
        <p className="mt-8 text-center text-sm text-zinc-500">
          Уже есть аккаунт?{" "}
          <Link href="/login" className="mm-link font-medium">
            Войти
          </Link>
        </p>
      </div>
    </main>
  );
}
