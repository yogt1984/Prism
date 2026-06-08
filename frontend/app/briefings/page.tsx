"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import BriefingListItem from "@/components/briefing/BriefingListItem";
import Pagination from "@/components/briefing/Pagination";
import TriggerBriefingButton from "@/components/briefing/TriggerBriefingButton";
import { useBriefingList, useTriggerBriefing, PAGE_SIZE } from "@/lib/hooks";

export default function BriefingsListPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const userId = (session?.user as Record<string, unknown> | undefined)
    ?.id as number | undefined;

  const [offset, setOffset] = useState(0);

  const { data: briefings = [], isLoading, error } = useBriefingList(userId, offset);

  const trigger = useTriggerBriefing(userId);

  const handleTrigger = () => {
    trigger.mutate(undefined, {
      onSuccess: (data) => {
        router.push(`/briefings/${data.id}`);
      },
    });
  };

  if (isLoading) {
    return (
      <main className="max-w-3xl mx-auto px-4 py-8" data-testid="briefings-loading">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Your Briefings</h1>
        </div>
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-16 bg-gray-100 animate-pulse rounded-lg"
            />
          ))}
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="max-w-3xl mx-auto px-4 py-8" data-testid="briefings-error">
        <h1 className="text-2xl font-bold mb-4">Your Briefings</h1>
        <p className="text-gray-500 mb-4">Could not load briefings</p>
        <button
          onClick={() => window.location.reload()}
          className="text-sm text-violet-600 hover:underline"
          data-testid="retry-btn"
        >
          Retry
        </button>
      </main>
    );
  }

  if (briefings.length === 0 && offset === 0) {
    return (
      <main className="max-w-3xl mx-auto px-4 py-8" data-testid="briefings-empty">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Your Briefings</h1>
        </div>
        <div className="text-center py-16">
          <p className="text-lg text-gray-600 mb-2">No briefings yet</p>
          <p className="text-sm text-gray-400 mb-6">
            Your first one arrives at 7am UTC
          </p>
          <TriggerBriefingButton
            onTrigger={handleTrigger}
            isPending={trigger.isPending}
          />
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-8" data-testid="briefings-list">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Your Briefings</h1>
        <TriggerBriefingButton
          onTrigger={handleTrigger}
          isPending={trigger.isPending}
        />
      </div>
      <div className="rounded-lg border border-gray-200 divide-y divide-gray-100">
        {briefings.map((b) => (
          <BriefingListItem key={b.id} briefing={b} />
        ))}
      </div>
      <div className="mt-4">
        <Pagination
          offset={offset}
          pageSize={PAGE_SIZE}
          itemCount={briefings.length}
          onPrevious={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
          onNext={() => setOffset((o) => o + PAGE_SIZE)}
        />
      </div>
    </main>
  );
}
