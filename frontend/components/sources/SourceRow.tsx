"use client";

import { useState } from "react";
import type { Source } from "@/lib/types";
import BiasLabelBadge from "@/components/story/BiasLabelBadge";
import CategoryPill from "@/components/dashboard/CategoryPill";
import TrustBar from "./TrustBar";
import StatusBadge from "./StatusBadge";
import LifecycleInfo from "./LifecycleInfo";

interface SourceRowProps {
  source: Source;
}

function getFaviconUrl(url: string): string {
  try {
    const hostname = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=32`;
  } catch {
    return "/icons/globe.svg";
  }
}

function FaviconImg({ url }: { url: string }) {
  const [errored, setErrored] = useState(false);
  const src = errored ? "/icons/globe.svg" : getFaviconUrl(url);

  return (
    <img
      src={src}
      onError={() => setErrored(true)}
      alt=""
      className="w-5 h-5 rounded"
      data-testid="favicon"
    />
  );
}

function getDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function getCategories(cats: string): string[] {
  return cats
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean);
}

/** Desktop table row */
export function SourceTableRow({ source }: SourceRowProps) {
  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50" data-testid="source-row">
      <td className="py-3 px-4">
        <div className="flex items-center gap-3">
          <FaviconImg url={source.url} />
          <div>
            <div className="font-medium text-gray-900 text-sm">{source.name}</div>
            <div className="text-xs text-gray-400">{getDomain(source.url)}</div>
          </div>
        </div>
      </td>
      <td className="py-3 px-4">
        <TrustBar value={source.trust_score} />
      </td>
      <td className="py-3 px-4">
        <BiasLabelBadge label={source.bias_label} />
      </td>
      <td className="py-3 px-4">
        <div className="flex flex-col gap-1">
          <StatusBadge status={source.status} />
          <LifecycleInfo source={source} />
        </div>
      </td>
      <td className="py-3 px-4 hidden lg:table-cell">
        <div className="flex flex-wrap gap-1">
          {getCategories(source.categories).map((c) => (
            <CategoryPill key={c} category={c} />
          ))}
        </div>
      </td>
      <td className="py-3 px-4">
        <a
          href={`/stories?source=${source.id}`}
          className="text-sm text-violet-600 hover:underline"
          data-testid="stories-link"
        >
          View
        </a>
      </td>
    </tr>
  );
}

/** Mobile card layout */
export function SourceCard({ source }: SourceRowProps) {
  return (
    <div
      className="rounded-lg border border-gray-200 p-4 space-y-3"
      data-testid="source-card"
    >
      <div className="flex items-center gap-3">
        <FaviconImg url={source.url} />
        <div>
          <div className="font-medium text-gray-900 text-sm">{source.name}</div>
          <div className="text-xs text-gray-400">{getDomain(source.url)}</div>
        </div>
      </div>
      <TrustBar value={source.trust_score} />
      <div className="flex items-center gap-2 flex-wrap">
        <StatusBadge status={source.status} />
        <BiasLabelBadge label={source.bias_label} />
        {getCategories(source.categories).map((c) => (
          <CategoryPill key={c} category={c} />
        ))}
      </div>
      <LifecycleInfo source={source} />
      <a
        href={`/stories?source=${source.id}`}
        className="text-sm text-violet-600 hover:underline"
        data-testid="stories-link"
      >
        View stories &rarr;
      </a>
    </div>
  );
}

export { getFaviconUrl, getDomain, getCategories };
