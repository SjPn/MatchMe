"use client";

import Link from "next/link";
import { useState } from "react";

export default function OnboardingPage() {
  const [step, setStep] = useState(0);

  if (step === 0) {
    return (
      <main className="mm-page-centered">
        <p className="text-sky-600 text-sm mb-2">Шаг 1</p>
        <h1 className="text-2xl font-semibold">Мы не про внешность</h1>
        <p className="mt-3 text-zinc-600">
          Мы сравниваем мышление и ценности — чтобы находить своих людей, а не «оценивать обложку».
        </p>
        <button type="button" onClick={() => setStep(1)} className="mm-btn-primary mt-10 px-8">
          Дальше
        </button>
      </main>
    );
  }

  return (
    <main className="mm-page-centered">
      <p className="text-sky-600 text-sm mb-2">Шаг 2</p>
      <h1 className="text-2xl font-semibold">10–15 вопросов</h1>
      <p className="mt-3 text-zinc-600">
        Твой профиль в MatchMe и лента людей с процентом совпадения и понятными формулировками.
      </p>
      <Link href="/register" className="mm-btn-primary mt-10 px-8 text-center">
        Поехали
      </Link>
    </main>
  );
}
