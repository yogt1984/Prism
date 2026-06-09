"use client";

import { useState, useDeferredValue } from "react";
import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";
import type { BiasLabel, Source, SourceStatus } from "@/lib/types";
import { useSources } from "@/lib/hooks";
import FilterChip from "@/components/sources/FilterChip";
import { SourceTableRow, SourceCard } from "@/components/sources/SourceRow";
import SourceStats from "@/components/sources/SourceStats";

type SortMode = "trust_desc" | "trust_asc" | "name_asc" | "bias";

const BIAS_ORDER: Record<string, number> = {
  left: 0,
  center_left: 1,
  center: 2,
  center_right: 3,
  right: 4,
  unknown: 5,
};

const BIAS_CHIPS: { label: string; value: BiasLabel | null; color?: string }[] = [
  { label: "All", value: null },
  { label: "Left", value: "left", color: "bg-blue-600" },
  { label: "Center-Left", value: "center_left", color: "bg-blue-300" },
  { label: "Center", value: "center", color: "bg-gray-400" },
  { label: "Center-Right", value: "center_right", color: "bg-red-300" },
  { label: "Right", value: "right", color: "bg-red-600" },
];

const STATUS_CHIPS: { label: string; value: SourceStatus | null; color?: string }[] = [
  { label: "All Statuses", value: null },
  { label: "Seed", value: "seed", color: "bg-gray-400" },
  { label: "Candidate", value: "candidate", color: "bg-yellow-400" },
  { label: "Probation", value: "probation", color: "bg-orange-400" },
  { label: "Trusted", value: "trusted", color: "bg-green-500" },
  { label: "Rejected", value: "rejected", color: "bg-red-500" },
];

function filterSources(
  sources: Source[],
  search: string,
  bias: BiasLabel | null,
  status: SourceStatus | null,
  sortBy: SortMode,
): Source[] {
  let filtered = sources;

  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.url.toLowerCase().includes(q),
    );
  }

  if (bias !== null) {
    filtered = filtered.filter((s) => s.bias_label === bias);
  }

  if (status !== null) {
    filtered = filtered.filter((s) => s.status === status);
  }

  return [...filtered].sort((a, b) => {
    switch (sortBy) {
      case "trust_desc":
        return b.trust_score - a.trust_score;
      case "trust_asc":
        return a.trust_score - b.trust_score;
      case "name_asc":
        return a.name.localeCompare(b.name);
      case "bias":
        return (
          (BIAS_ORDER[a.bias_label] ?? 5) - (BIAS_ORDER[b.bias_label] ?? 5)
        );
    }
  });
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6" data-testid="loading-skeleton">
      <div className="space-y-3">
        {Array.from({ length: 10 }, (_, i) => (
          <div
            key={i}
            className="h-12 bg-gray-100 rounded-md animate-pulse"
          />
        ))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {Array.from({ length: 3 }, (_, i) => (
          <div
            key={i}
            className="h-24 bg-gray-100 rounded-lg animate-pulse"
          />
        ))}
      </div>
    </div>
  );
}

export default function SourcesPage() {
  const { status } = useSession();
  const { data: sources, isLoading, isError, refetch } = useSources();

  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [biasFilter, setBiasFilter] = useState<BiasLabel | null>(null);
  const [statusFilter, setStatusFilter] = useState<SourceStatus | null>(null);
  const [sortBy, setSortBy] = useState<SortMode>("trust_desc");

  if (status === "unauthenticated") {
    redirect("/auth/signin");
  }

  const allSources = sources ?? [];
  const filtered = filterSources(allSources, deferredSearch, biasFilter, statusFilter, sortBy);

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">News Sources</h1>
        <p className="text-gray-500 text-sm mt-1">
          Every source Prism tracks, with trust, bias, and lifecycle status
        </p>
        {!isLoading && !isError && (
          <p className="text-sm text-gray-400 mt-1" data-testid="source-count">
            {allSources.length} source{allSources.length !== 1 ? "s" : ""}
          </p>
        )}
      </div>

      {isLoading && <LoadingSkeleton />}

      {isError && (
        <div className="text-center py-12" data-testid="error-state">
          <p className="text-gray-600">Could not load sources</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 text-sm text-violet-600 hover:underline"
            data-testid="retry-btn"
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && !isError && (
        <>
          {/* Filter Bar */}
          <div className="space-y-3" data-testid="filter-bar">
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                placeholder="Search sources..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="px-3 py-2 text-sm border border-gray-200 rounded-md w-full sm:w-64 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                data-testid="search-input"
              />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortMode)}
                className="px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-violet-500"
                data-testid="sort-select"
              >
                <option value="trust_desc">Trust: High → Low</option>
                <option value="trust_asc">Trust: Low → High</option>
                <option value="name_asc">Name: A → Z</option>
                <option value="bias">Bias: Left → Right</option>
              </select>
            </div>
            <div className="flex flex-wrap gap-2" data-testid="bias-filters">
              {BIAS_CHIPS.map((chip) => (
                <FilterChip
                  key={chip.label}
                  label={chip.label}
                  active={biasFilter === chip.value}
                  onClick={() => setBiasFilter(chip.value)}
                  color={chip.color}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-2" data-testid="status-filters">
              {STATUS_CHIPS.map((chip) => (
                <FilterChip
                  key={chip.label}
                  label={chip.label}
                  active={statusFilter === chip.value}
                  onClick={() => setStatusFilter(chip.value)}
                  color={chip.color}
                />
              ))}
            </div>
          </div>

          {/* Empty states */}
          {filtered.length === 0 && deferredSearch && (
            <div className="text-center py-12" data-testid="empty-search">
              <p className="text-gray-600">
                No sources match &lsquo;{deferredSearch}&rsquo;
              </p>
              <button
                type="button"
                onClick={() => setSearch("")}
                className="mt-3 text-sm text-violet-600 hover:underline"
                data-testid="clear-search-btn"
              >
                Clear search
              </button>
            </div>
          )}

          {filtered.length === 0 && !deferredSearch && biasFilter && (
            <div className="text-center py-12" data-testid="empty-bias">
              <p className="text-gray-600">
                No {biasFilter.replace("_", " ")} sources found
              </p>
              <button
                type="button"
                onClick={() => setBiasFilter(null)}
                className="mt-3 text-sm text-violet-600 hover:underline"
                data-testid="reset-bias-btn"
              >
                Reset filter
              </button>
            </div>
          )}

          {filtered.length === 0 && !deferredSearch && !biasFilter && statusFilter && (
            <div className="text-center py-12" data-testid="empty-status">
              <p className="text-gray-600">
                No {statusFilter} sources found
              </p>
              <button
                type="button"
                onClick={() => setStatusFilter(null)}
                className="mt-3 text-sm text-violet-600 hover:underline"
                data-testid="reset-status-btn"
              >
                Reset filter
              </button>
            </div>
          )}

          {/* Desktop table */}
          {filtered.length > 0 && (
            <div className="hidden md:block" data-testid="source-table-container">
              <table className="w-full" data-testid="source-table">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-xs text-gray-500 uppercase tracking-wide">
                    <th className="py-2 px-4">Source</th>
                    <th className="py-2 px-4">Trust Score</th>
                    <th className="py-2 px-4">Bias</th>
                    <th className="py-2 px-4">Status</th>
                    <th className="py-2 px-4 hidden lg:table-cell">Categories</th>
                    <th className="py-2 px-4">Stories</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((source) => (
                    <SourceTableRow key={source.id} source={source} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Mobile cards */}
          {filtered.length > 0 && (
            <div className="md:hidden space-y-3" data-testid="source-cards-container">
              {filtered.map((source) => (
                <SourceCard key={source.id} source={source} />
              ))}
            </div>
          )}

          {/* Stats */}
          {allSources.length > 0 && (
            <SourceStats sources={allSources} />
          )}
        </>
      )}
    </main>
  );
}

export { filterSources, BIAS_ORDER, BIAS_CHIPS, STATUS_CHIPS };
export type { SortMode };
