"use client";

import Link from "next/link";
import { useMemo } from "react";

export type ThreadPostOut = {
  id: number;
  author: { id: number | null; display_name: string | null };
  parent_id: number | null;
  root_id: number;
  kind: string;
  quote_post_id: number | null;
  quote_preview?: ThreadPostOut | null;
  body: string;
  created_at: string;
  is_system: boolean;
  visibility: string;
  media: { id: number; url: string; mime: string }[];
  reply_count: number;
  like_count: number;
  liked_by_me: boolean;
  repost_count: number;
  quote_count: number;
  topic_axis_slugs: string[];
};

function timeAgo(iso: string): string {
  const t = new Date(iso).getTime();
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
}

export function ThreadPostCard(props: {
  post: ThreadPostOut;
  compact?: boolean;
  href?: string;
  withCard?: boolean;
  withLink?: boolean;
}) {
  const { post, compact, href, withCard = true, withLink = true } = props;
  const author = post.author.display_name || (post.is_system ? "MatchMe" : "—");

  const snippet = useMemo(() => {
    const t = post.body.trim().replace(/\s+/g, " ");
    const n = compact ? 220 : 360;
    if (t.length <= n) return t;
    return `${t.slice(0, n - 1)}…`;
  }, [post.body, compact]);

  const content = (
    <div className={withCard ? "mm-card py-4" : ""}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-zinc-500">
            {post.author.id ? (
              <Link
                href={`/users/${post.author.id}`}
                className="text-zinc-800 font-medium hover:text-sky-700"
                onClick={(e) => {
                  // prevent parent post link navigation when author is clicked
                  e.stopPropagation();
                }}
              >
                {author}
              </Link>
            ) : (
              <span className="text-zinc-800 font-medium">{author}</span>
            )}{" "}
            · {timeAgo(post.created_at)}
          </p>
          {post.kind === "repost" || post.kind === "quote" ? (
            <p className="mt-2 text-[11px] text-zinc-500">
              {post.kind === "repost" ? "Репост" : "Цитата"}
            </p>
          ) : null}
          <p className={`mt-2 text-sm text-zinc-800 leading-relaxed ${compact ? "line-clamp-4" : "line-clamp-6"}`}>
            {post.kind === "repost" ? "" : snippet}
          </p>
          {post.quote_preview ? (
            <div className="mt-3 rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2">
              <p className="text-xs text-zinc-600 line-clamp-3">
                <span className="text-zinc-500">↳ </span>
                {post.quote_preview.body?.trim() ? post.quote_preview.body.trim() : "Пост"}
              </p>
            </div>
          ) : null}
        </div>
      </div>
      <div className="mt-3 flex items-center gap-4 text-xs text-zinc-500">
        <span>💬 {post.reply_count}</span>
        <span>♥ {post.like_count}</span>
        <span>↻ {post.repost_count}</span>
        <span>❝ {post.quote_count}</span>
        <span className="text-zinc-700">·</span>
        <span className="text-zinc-600">Открыть</span>
      </div>
    </div>
  );

  if (!withLink) return content;
  return (
    <Link href={href || `/posts/${post.id}`} className="block">
      {content}
    </Link>
  );
}

