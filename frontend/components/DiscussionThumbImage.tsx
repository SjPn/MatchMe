"use client";

import Image from "next/image";
import { apiUrl } from "@/lib/api";

export function DiscussionThumbImage({ postId, title }: { postId: number; title: string }) {
  const src = apiUrl(`/discussions/posts/${postId}/image`);
  return (
    <Image
      src={src}
      alt={title.trim() ? `Миниатюра: ${title}` : "Миниатюра поста"}
      width={56}
      height={56}
      className="h-14 w-14 rounded-lg object-cover border border-zinc-700 shrink-0"
      unoptimized
    />
  );
}
