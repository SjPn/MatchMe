import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main className="mm-page text-sm leading-relaxed scrollbar-thin">
      <Link href="/register" className="text-sm text-zinc-500 hover:text-emerald-400/90 transition-colors">
        ← К регистрации
      </Link>
      <h1 className="mm-h1 mt-8">Конфиденциальность (MVP)</h1>
      <p className="text-zinc-500 mt-2 text-xs">Черновик. Для реальных пользователей и юрисдикций нужна доработка.</p>

      <section className="mt-8 space-y-4 text-zinc-300">
        <p>
          <strong className="text-zinc-200">Какие данные:</strong> email и пароль для учётной записи, имя
          (псевдоним), ответы на вопросы онбординга, данные о лайках, матчах, сообщениях в чатах и участии в
          групповых комнатах. Технические логи могут содержать IP и метаданные запросов.
        </p>
        <p>
          <strong className="text-zinc-200">Зачем:</strong> регистрация, расчёт совпадений, отображение ленты и
          чатов, безопасность и противодействие злоупотреблениям.
        </p>
        <p>
          <strong className="text-zinc-200">Показ другим:</strong> в ленте и профилях другие пользователи видят
          псевдоним и результаты совместимости, но не ваш email. В групповых чатах виден псевдоним и сообщения в
          комнате.
        </p>
        <p>
          <strong className="text-zinc-200">Хранение:</strong> данные хранятся в базе приложения; в разработке
          часто используется локальный SQLite, на проде — отдельная БД с резервным копированием по вашей
          инфраструктуре.
        </p>
        <p>
          <strong className="text-zinc-200">Ваши действия:</strong> вы можете запросить удаление аккаунта у
          оператора сервиса (в MVP — через контакт разработчика); блокировки и жалобы доступны в интерфейсе там,
          где реализовано.
        </p>
      </section>
    </main>
  );
}
