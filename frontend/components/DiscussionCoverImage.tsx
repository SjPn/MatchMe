"use client";

import Image from "next/image";
import { apiUrl } from "@/lib/api";

/** Обложка поста обсуждения; same-origin `/api/...` через прокси Next. */
export function DiscussionCoverImage({
  postId,
  title,
  className,
}: {
  postId: number;
  title: string;
  className?: string;
}) {
  const src = apiUrl(`/discussions/posts/${postId}/image`);
  const alt = title.trim() ? `Обложка поста: ${title}` : "Обложка поста";
  return (
    <Image
      src={src}
      alt={alt}
      width={680}
      height={256}
      className={className ?? "w-full max-h-64 h-auto rounded-2xl object-cover border border-zinc-800/80 shadow-mm-card"}
      sizes="(max-width: 680px) 100vw, 680px"
      priority={false}
      unoptimized
    />
  );
}
