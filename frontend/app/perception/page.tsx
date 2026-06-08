"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";
import {
  useActiveKeywords,
  useLatestPerception,
  usePerceptionHistory,
  useAddKeyword,
  useRemoveKeyword,
} from "@/lib/hooks";
import type { Keyword, PerceptionSnapshot } from "@/lib/types";
import { ApiError } from "@/lib/api";
import KeywordOverviewCard from "@/components/perception/KeywordOverviewCard";
import DetailPanel from "@/components/perception/DetailPanel";
import AddKeywordModal from "@/components/perception/AddKeywordModal";

function useKeywordData(keywordId: number) {
  const perception = useLatestPerception(keywordId);
  const history = usePerceptionHistory(keywordId);
  return { perception, history };
}

function KeywordCardWrapper({
  keyword,
  onExpand,
  onRemove,
}: {
  keyword: Keyword;
  onExpand: () => void;
  onRemove: () => void;
}) {
  const { perception, history } = useKeywordData(keyword.id);

  return (
    <KeywordOverviewCard
      keyword={keyword}
      latest={perception.data ?? null}
      history={history.data ?? []}
      isHistoryLoading={history.isLoading}
      onExpand={onExpand}
      onRemove={onRemove}
    />
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div
      className="text-center py-20 space-y-4"
      data-testid="empty-state"
    >
      <div className="text-5xl">📡</div>
      <h2 className="text-lg font-semibold text-gray-900">
        Start tracking a topic
      </h2>
      <p className="text-sm text-gray-500 max-w-md mx-auto">
        Add keywords to monitor how media frames them over time. Track
        perception pressure, sentiment, and attention volume.
      </p>
      <button
        type="button"
        onClick={onAdd}
        className="px-4 py-2 text-sm font-medium rounded-md bg-violet-600 text-white hover:bg-violet-700"
        data-testid="empty-add-btn"
      >
        Track your first keyword
      </button>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div
      className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
      data-testid="loading-skeleton"
    >
      {Array.from({ length: 3 }, (_, i) => (
        <div
          key={i}
          className="rounded-lg border border-gray-200 p-4 space-y-3 animate-pulse"
        >
          <div className="h-5 bg-gray-100 rounded w-24" />
          <div className="h-8 bg-gray-100 rounded w-16" />
          <div className="grid grid-cols-4 gap-2">
            {Array.from({ length: 4 }, (_, j) => (
              <div key={j} className="h-8 bg-gray-50 rounded" />
            ))}
          </div>
          <div className="h-20 bg-gray-50 rounded" />
        </div>
      ))}
    </div>
  );
}

export default function PerceptionPage() {
  const { status } = useSession();
  const {
    data: keywords,
    isLoading,
    isError,
    refetch,
  } = useActiveKeywords();

  const [selectedKeywordId, setSelectedKeywordId] = useState<number | null>(
    null,
  );
  const [modalOpen, setModalOpen] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const addKeyword = useAddKeyword();
  const removeKeyword = useRemoveKeyword();

  if (status === "unauthenticated") {
    redirect("/auth/signin");
  }

  const allKeywords = keywords ?? [];
  const selectedKeyword = allKeywords.find(
    (k) => k.id === selectedKeywordId,
  );

  function handleAdd(payload: {
    keyword: string;
    aliases: string;
    category: string;
  }) {
    setAddError(null);
    addKeyword.mutate(payload, {
      onSuccess: () => {
        setModalOpen(false);
      },
      onError: (err) => {
        if (err instanceof ApiError && err.status === 409) {
          setAddError("Already tracking this keyword");
        } else {
          setAddError("Could not add keyword — try again");
        }
      },
    });
  }

  function handleRemove(keywordId: number) {
    if (selectedKeywordId === keywordId) {
      setSelectedKeywordId(null);
    }
    removeKeyword.mutate(keywordId);
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Perception Tracker
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            Monitor how media frames your tracked topics over time
          </p>
        </div>
        {!isLoading && !isError && allKeywords.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setAddError(null);
              setModalOpen(true);
            }}
            className="px-4 py-2 text-sm font-medium rounded-md bg-violet-600 text-white hover:bg-violet-700"
            data-testid="add-keyword-btn"
          >
            + Add Keyword
          </button>
        )}
      </div>

      {/* Loading */}
      {isLoading && <LoadingSkeleton />}

      {/* Error */}
      {isError && (
        <div className="text-center py-12" data-testid="error-state">
          <p className="text-gray-600">Could not load keywords</p>
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

      {/* Empty */}
      {!isLoading && !isError && allKeywords.length === 0 && (
        <EmptyState onAdd={() => setModalOpen(true)} />
      )}

      {/* Content */}
      {!isLoading && !isError && allKeywords.length > 0 && (
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Keyword grid */}
          <div
            className={`grid grid-cols-1 md:grid-cols-2 ${
              selectedKeyword ? "lg:grid-cols-2" : "lg:grid-cols-3"
            } gap-4 ${selectedKeyword ? "lg:w-3/5" : "w-full"}`}
            data-testid="keyword-grid"
          >
            {allKeywords.map((kw) => (
              <KeywordCardWrapper
                key={kw.id}
                keyword={kw}
                onExpand={() => setSelectedKeywordId(kw.id)}
                onRemove={() => handleRemove(kw.id)}
              />
            ))}
          </div>

          {/* Detail panel */}
          {selectedKeyword && (
            <div className="lg:w-2/5">
              <DetailPanel
                key={selectedKeyword.id}
                keyword={selectedKeyword}
                onClose={() => setSelectedKeywordId(null)}
              />
            </div>
          )}
        </div>
      )}

      {/* Add keyword modal */}
      <AddKeywordModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleAdd}
        isPending={addKeyword.isPending}
        error={addError}
      />
    </main>
  );
}
