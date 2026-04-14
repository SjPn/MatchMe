import { api } from "./api";

/** Куда вести после логина / регистрации: тест или основное приложение. */
export async function pathAfterAuth(): Promise<string> {
  const me = await api<{ onboarding_step: string }>("/auth/me");
  if (me.onboarding_step === "test_completed") {
    return "/feed";
  }
  return "/test";
}
