import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 py-16 text-zinc-900 bg-white">
      <div className="text-center max-w-lg">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-600 mb-5">MatchMe</p>
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-balance leading-tight text-zinc-900">
          Найди друзей по взглядам, а не по внешности
        </h1>
        <p className="mt-5 text-zinc-600 text-base leading-relaxed max-w-md mx-auto">
          Короткий тест ценностей → совпадения → честное сравнение до фото.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row gap-3 justify-center w-full max-w-sm mx-auto">
          <Link href="/onboarding" className="mm-btn-primary px-8 py-3.5 text-base">
            Начать
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-xl border border-zinc-200 bg-white px-8 py-3.5 text-base font-medium text-zinc-800 hover:border-sky-300 hover:bg-sky-50 transition active:scale-[0.98]"
          >
            Уже есть аккаунт
          </Link>
        </div>
        <p className="mt-14 text-xs text-zinc-600">
          <Link href="/register" className="mm-link">
            Регистрация
          </Link>
          <span className="mx-2 text-zinc-700">·</span>
          <span className="text-zinc-600">FastAPI · PostgreSQL</span>
        </p>
      </div>
    </main>
  );
}
