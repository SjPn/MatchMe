"use client";

import type { ReactNode } from "react";

export type ReplyPreview = {
  id: number;
  sender_id: number;
  body_snippet: string;
};

export type Attachment = {
  original_name: string;
  mime: string;
  url: string;
};

type Props = {
  mine: boolean;
  headerLeft: ReactNode;
  onReply?: () => void;
  onReport?: () => void;
  body?: string | null;
  replyTo?: ReplyPreview | null;
  replyPrefix?: string | null;
  attachment?: Attachment | null;
  onAttachmentClick?: () => void;
};

export function MessageBubble({
  mine,
  headerLeft,
  onReply,
  onReport,
  body,
  replyTo,
  replyPrefix,
  attachment,
  onAttachmentClick,
}: Props) {
  return (
    <div
      className={`rounded-xl border px-3 py-2 text-sm max-w-[min(100%,24rem)] ${
        mine ? "ml-auto bg-emerald-500/15 border-emerald-500/40" : "mr-auto bg-zinc-900/60 border-zinc-800"
      }`}
    >
      <div className="flex justify-between items-start gap-2 mb-1">
        <div className="text-xs text-zinc-500 truncate">{headerLeft}</div>
        <div className="flex gap-1 shrink-0">
          {onReply ? (
            <button
              type="button"
              className="text-[10px] text-zinc-500 hover:text-emerald-400"
              onClick={onReply}
            >
              Ответить
            </button>
          ) : null}
          {!mine && onReport ? (
            <button
              type="button"
              className="text-[10px] text-zinc-600 hover:text-amber-500"
              onClick={onReport}
            >
              Жалоба
            </button>
          ) : null}
        </div>
      </div>

      {replyTo ? (
        <div
          className={`mb-2 rounded-lg border px-2 py-1 text-xs ${
            mine ? "border-emerald-500/30 bg-black/20" : "border-zinc-700 bg-black/20"
          }`}
        >
          {replyPrefix ? <span className="text-zinc-500">{replyPrefix}</span> : null}
          <span className="text-zinc-300 line-clamp-2">{replyTo.body_snippet}</span>
        </div>
      ) : null}

      {body ? <p className="whitespace-pre-wrap break-words">{body}</p> : null}

      {attachment ? (
        <div className="mt-2 text-xs">
          <a
            href="#"
            className="text-emerald-400 underline break-all"
            onClick={(e) => {
              e.preventDefault();
              onAttachmentClick?.();
            }}
          >
            {attachment.original_name}
          </a>
          <span className="text-zinc-500 ml-2">({attachment.mime})</span>
        </div>
      ) : null}
    </div>
  );
}

