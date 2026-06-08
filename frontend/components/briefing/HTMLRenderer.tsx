"use client";

import DOMPurify from "dompurify";
import { useMemo } from "react";

const ALLOWED_TAGS = [
  "h1", "h2", "h3", "p", "a", "em", "strong",
  "ul", "ol", "li", "br", "span",
];
const ALLOWED_ATTRS = ["href", "target", "rel"];

function sanitize(html: string): string {
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.tagName === "A") {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  });

  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ALLOWED_ATTRS,
  });

  DOMPurify.removeAllHooks();
  return clean;
}

export default function HTMLRenderer({ html }: { html: string }) {
  const clean = useMemo(() => sanitize(html), [html]);

  return (
    <article
      className="prose prose-neutral max-w-none"
      data-testid="html-renderer"
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
}

export { ALLOWED_TAGS, ALLOWED_ATTRS };
