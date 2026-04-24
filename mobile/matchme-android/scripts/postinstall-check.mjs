// Подсказка при первом clone — не падает, если android/ ещё нет
import { access } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const android = join(root, "android");
try {
  await access(android);
} catch {
  console.log(
    "[matchme-android] Папка android/ ещё не создана. Выполни: npx cap add android"
  );
}
