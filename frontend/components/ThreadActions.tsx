"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { ThreadPostOut } from "@/components/ThreadComposerSheet";

export function ThreadActions(props: {
  post: ThreadPostOut;
  onPostChange?: (next: ThreadPostOut) => void;
  onReply?: () => void;
  onQuote?: () => void;
  onRepost?: () => void;
}) {
  const { post, onPostChange } = props;
  const [busy, setBusy] = useState(false);

  async function toggleLike() {
    if (busy) return;
    setBusy(true);
    const optimistic: ThreadPostOut = {
      ...post,
      liked_by_me: !post.liked_by_me,
      like_count: Math.max(0, post.like_count + (post.liked_by_me ? -1 : 1)),
    };
    onPostChange?.(optimistic);
    try {
      if (post.liked_by_me) await api(`/posts/${post.id}/like`, { method: "DELETE" });
      else await api(`/posts/${post.id}/like`, { method: "POST" });
    } catch {
      onPostChange?.(post);
    } finally {
      setBusy(false);
    }
  }

  async function doRepost() {
    if (busy) return;
    setBusy(true);
    try {
      await api(`/posts/${post.id}/repost`, { method: "POST" });
      props.onRepost?.();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 flex items-center justify-between text-xs text-zinc-500">
      <button type="button" className="px-2 py-1 rounded-lg hover:bg-zinc-100" onClick={props.onReply}>
        💬 Ответить
      </button>
      <button type="button" className="px-2 py-1 rounded-lg hover:bg-zinc-100" onClick={() => void doRepost()}>
        ↻ Репост
      </button>
      <button type="button" className="px-2 py-1 rounded-lg hover:bg-zinc-100" onClick={props.onQuote}>
        ❝ Цитата
      </button>
      <button
        type="button"
        className={`px-2 py-1 rounded-lg hover:bg-zinc-100 ${post.liked_by_me ? "text-sky-600" : ""}`}
        onClick={() => void toggleLike()}
        aria-pressed={post.liked_by_me}
      >
        ♥ {post.like_count}
      </button>
    </div>
  );
}

