"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import { pathAfterAuth } from "@/lib/postAuthRedirect";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
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
        <h1 className="mm-h1 text-center">Вход</h1>
        <p className="mm-lead text-center mt-3">С возвращением</p>
        <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-5">
          <label className="mm-label">
            <span>Email</span>
            <input
              type="email"
              className="mm-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>
          <label className="mm-label">
            <span>Пароль</span>
            <input
              type="password"
              className="mm-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          {error ? <p className="mm-error">{error}</p> : null}
          <button type="submit" disabled={loading} className="mm-btn-primary w-full py-3.5">
            {loading ? "Входим…" : "Войти"}
          </button>
        </form>
        <p className="mt-8 text-center text-sm text-zinc-500">
          Нет аккаунта?{" "}
          <Link href="/register" className="mm-link font-medium">
            Регистрация
          </Link>
        </p>
      </div>
    </main>
  );
}
