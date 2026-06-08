"use client";

import { useState } from "react";
import PerspectiveCard from "./PerspectiveCard";
import type { Perspective, Source } from "@/lib/types";

type ViewMode = "side-by-side" | "stacked" | "tabbed";

interface PerspectiveViewerProps {
  perspectives: Perspective[];
  sourceMap: Map<number, Source>;
}

export default function PerspectiveViewer({
  perspectives,
  sourceMap,
}: PerspectiveViewerProps) {
  const [mode, setMode] = useState<ViewMode>("side-by-side");
  const [activeTab, setActiveTab] = useState(0);

  if (perspectives.length === 0) {
    return (
      <section data-testid="perspectives-analyzing">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Perspectives
        </h2>
        <p className="text-sm text-gray-500">
          This story is being analyzed &mdash; perspectives coming soon
        </p>
      </section>
    );
  }

  const singlePerspective = perspectives.length === 1;

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Perspectives
        </h2>
        {!singlePerspective && (
          <div className="flex gap-1" data-testid="view-toggle">
            {(["side-by-side", "stacked", "tabbed"] as ViewMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-2 py-1 text-xs rounded ${
                  mode === m
                    ? "bg-violet-100 text-violet-700 font-medium"
                    : "text-gray-500 hover:bg-gray-100"
                }`}
              >
                {m === "side-by-side" ? "Grid" : m === "stacked" ? "Stack" : "Tabs"}
              </button>
            ))}
          </div>
        )}
      </div>

      {singlePerspective && (
        <p className="text-xs text-gray-400 mb-2">
          Only one source covered this story
        </p>
      )}

      {mode === "side-by-side" && (
        <div
          className={`grid gap-4 ${
            singlePerspective
              ? "grid-cols-1"
              : perspectives.length === 2
                ? "grid-cols-1 lg:grid-cols-2"
                : "grid-cols-1 lg:grid-cols-2 xl:grid-cols-3"
          }`}
          data-testid="perspective-grid"
        >
          {perspectives.map((p) => (
            <PerspectiveCard
              key={p.id}
              perspective={p}
              source={sourceMap.get(p.source_id)}
            />
          ))}
        </div>
      )}

      {mode === "stacked" && (
        <div className="space-y-4" data-testid="perspective-stack">
          {perspectives.map((p) => (
            <PerspectiveCard
              key={p.id}
              perspective={p}
              source={sourceMap.get(p.source_id)}
            />
          ))}
        </div>
      )}

      {mode === "tabbed" && (
        <div data-testid="perspective-tabs">
          <div className="flex gap-2 border-b border-gray-200 mb-4 overflow-x-auto">
            {perspectives.map((p, i) => {
              const src = sourceMap.get(p.source_id);
              return (
                <button
                  key={p.id}
                  onClick={() => setActiveTab(i)}
                  className={`px-3 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
                    activeTab === i
                      ? "border-violet-600 text-violet-700 font-medium"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {src?.name ?? `Source #${p.source_id}`}
                </button>
              );
            })}
          </div>
          <PerspectiveCard
            perspective={perspectives[activeTab]}
            source={sourceMap.get(perspectives[activeTab].source_id)}
          />
        </div>
      )}
    </section>
  );
}
