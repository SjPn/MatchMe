"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 text-zinc-900 bg-white">
      <p className="text-sm font-medium text-red-600 mb-2">Что-то пошло не так</p>
      <p className="text-xs text-zinc-500 text-center max-w-md mb-8 leading-relaxed">
        {error.message || "Не удалось отобразить страницу."}
      </p>
      <button type="button" onClick={() => reset()} className="mm-btn-primary px-6">
        Попробовать снова
      </button>
    </main>
  );
}
