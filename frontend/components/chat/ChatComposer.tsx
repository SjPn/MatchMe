"use client";

import { useMemo, useRef, useState } from "react";
import { useAutosizeTextarea } from "@/lib/hooks/useAutosizeTextarea";

type Props = {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled?: boolean;
  placeholder?: string;
  maxLines?: number;

  /** Show file picker row (direct chat) */
  file?: {
    accept?: string;
    disabled?: boolean;
    onPick: (f: File | null) => void;
  };

  /** Emoji list. If provided, show a toggle button + picker */
  emojis?: string[];
  /** Place emoji button beside file picker (direct chat) */
  emojiButtonOnFileRow?: boolean;

  /** Called when user taps outside input (optional) */
  onBlurKeyboard?: () => void;
};

export function ChatComposer({
  value,
  onChange,
  onSend,
  disabled,
  placeholder = "Сообщение",
  maxLines = 7,
  file,
  emojis,
  emojiButtonOnFileRow = false,
  onBlurKeyboard,
}: Props) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [emojiOpen, setEmojiOpen] = useState(false);

  const { resetHeight } = useAutosizeTextarea(inputRef, value, { maxLines });

  const emojiList = useMemo(() => (emojis && emojis.length ? emojis : []), [emojis]);

  function hideKeyboard() {
    try {
      inputRef.current?.blur();
    } catch {
      /* ignore */
    }
    onBlurKeyboard?.();
  }

  function insertAtCursor(text: string) {
    const el = inputRef.current;
    if (!el) {
      onChange(value ? `${value}${text}` : text);
      return;
    }
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const next = `${value.slice(0, start)}${text}${value.slice(end)}`;
    onChange(next);
    const caret = start + text.length;
    requestAnimationFrame(() => {
      try {
        el.focus();
        el.setSelectionRange(caret, caret);
      } catch {
        /* ignore */
      }
    });
  }

  function sendAndReset() {
    if (disabled) return;
    if (!value.trim()) return;
    onSend();
    setEmojiOpen(false);
    hideKeyboard();
    resetHeight();
    if (fileRef.current) fileRef.current.value = "";
  }

  const showEmojiButton = emojiList.length > 0;

  const EmojiButton = showEmojiButton ? (
    <button
      type="button"
      className="h-9 w-9 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-600 text-lg leading-none flex items-center justify-center shrink-0"
      onClick={() => setEmojiOpen((v) => !v)}
      aria-label="Смайлы"
      disabled={disabled}
    >
      🙂
    </button>
  ) : null;

  const EmojiPicker =
    showEmojiButton && emojiOpen ? (
      <div className="flex flex-wrap gap-1.5">
        {emojiList.map((s) => (
          <button
            key={s}
            type="button"
            className="text-lg leading-none px-1.5 py-0.5 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-600"
            onClick={() => {
              insertAtCursor(s);
              setEmojiOpen(false);
            }}
            disabled={disabled}
          >
            {s}
          </button>
        ))}
      </div>
    ) : null;

  return (
    <div
      className="border-t border-white/[0.06] bg-zinc-950/90 backdrop-blur-md p-4 flex flex-col gap-2 shrink-0 supports-[backdrop-filter]:bg-zinc-950/75"
      style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
    >
      {file ? (
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            className="min-w-0 flex-1 text-xs text-zinc-400 file:mr-2 file:rounded file:border-0 file:bg-zinc-800 file:px-2 file:py-1"
            accept={file.accept}
            disabled={Boolean(disabled || file.disabled)}
            onChange={(e) => file.onPick(e.target.files?.[0] ?? null)}
          />
          {emojiButtonOnFileRow ? EmojiButton : null}
        </div>
      ) : null}

      {emojiButtonOnFileRow ? EmojiPicker : null}

      <div className="flex items-center gap-2">
        <textarea
          ref={inputRef}
          rows={1}
          className="flex-1 rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm leading-5 resize-none overflow-hidden"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              sendAndReset();
            }
          }}
          placeholder={placeholder}
          disabled={disabled}
        />

        {!emojiButtonOnFileRow ? EmojiButton : null}

        <button
          type="button"
          disabled={Boolean(disabled || !value.trim())}
          className="rounded-lg bg-emerald-500 text-zinc-950 px-4 py-2 text-sm font-medium disabled:opacity-40"
          onClick={() => sendAndReset()}
        >
          Отправить
        </button>
      </div>

      {!emojiButtonOnFileRow ? EmojiPicker : null}
    </div>
  );
}

