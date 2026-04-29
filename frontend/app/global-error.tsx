"use client";

/**
 * Срабатывает при ошибке в корневом layout. Должен сам задать html/body (документация Next.js).
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-white text-zinc-900 antialiased flex flex-col items-center justify-center px-6">
        <p className="text-sm font-medium text-red-600 mb-2">Критическая ошибка интерфейса</p>
        <p className="text-xs text-zinc-500 text-center max-w-md mb-8 leading-relaxed">
          {error.message || "Перезагрузите страницу или очистите кэш .next при повторении."}
        </p>
        <button
          type="button"
          onClick={() => reset()}
          className="rounded-xl bg-sky-400 text-white font-medium py-2.5 px-4 text-sm shadow-lg shadow-sky-900/15 hover:bg-sky-500 transition"
        >
          Попробовать снова
        </button>
      </body>
    </html>
  );
}
