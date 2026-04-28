import { useEffect } from "react";

type Options = {
  /** Maximum number of visible lines before scrolling inside textarea */
  maxLines?: number;
};

function px(n: string | null | undefined): number {
  const v = Number.parseFloat(n || "0");
  return Number.isFinite(v) ? v : 0;
}

function autosize(el: HTMLTextAreaElement, maxLines: number) {
  el.style.height = "auto";
  const cs = window.getComputedStyle(el);
  const lineH = px(cs.lineHeight) || 20;
  const maxH =
    lineH * maxLines +
    px(cs.paddingTop) +
    px(cs.paddingBottom) +
    px(cs.borderTopWidth) +
    px(cs.borderBottomWidth);
  const next = Math.min(el.scrollHeight, maxH);
  el.style.height = `${next}px`;
  el.style.overflowY = el.scrollHeight > maxH ? "auto" : "hidden";
}

/** Autosize a textarea vertically up to maxLines. */
export function useAutosizeTextarea(
  ref: React.RefObject<HTMLTextAreaElement | null>,
  value: string,
  opts: Options = {}
) {
  const maxLines = Math.max(1, Math.min(30, opts.maxLines ?? 7));

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    autosize(el, maxLines);
  }, [ref, value, maxLines]);

  useEffect(() => {
    function onResize() {
      const el = ref.current;
      if (!el) return;
      autosize(el, maxLines);
    }
    window.addEventListener("resize", onResize);
    window.addEventListener("orientationchange", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
    };
  }, [ref, maxLines]);

  return {
    resetHeight() {
      const el = ref.current;
      if (!el) return;
      el.style.height = "auto";
      el.style.overflowY = "hidden";
    },
  };
}

