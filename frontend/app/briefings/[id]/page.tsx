"use client";

import { useParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useEffect, useRef } from "react";
import ReaderHeader from "@/components/briefing/ReaderHeader";
import HTMLRenderer from "@/components/briefing/HTMLRenderer";
import PlainTextRenderer from "@/components/briefing/PlainTextRenderer";
import BriefingNav from "@/components/briefing/BriefingNav";
import { useBriefingDetailById, useBriefingList, useRecordEngagement } from "@/lib/hooks";
import { useQueryClient } from "@tanstack/react-query";
import type { Briefing } from "@/lib/types";

export default function BriefingReaderPage() {
  const params = useParams();
  const briefingId = params?.id ? Number(params.id) : undefined;
  const { data: session } = useSession();
  const userId = (session?.user as Record<string, unknown> | undefined)
    ?.id as number | undefined;
  const queryClient = useQueryClient();

  const { data: briefing, isLoading, error } = useBriefingDetailById(
    userId,
    briefingId,
  );
  const engagement = useRecordEngagement();

  // Record 'open' once on mount
  const openRecorded = useRef(false);
  useEffect(() => {
    if (userId && briefingId && !openRecorded.current) {
      openRecorded.current = true;
      engagement.mutate({
        user_id: userId,
        cluster_id: briefingId,
        action: "open",
        read_time_sec: 0,
      });
    }
  }, [userId, briefingId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Record 'read' with accumulated time on unmount
  const mountTime = useRef(Date.now());
  useEffect(() => {
    return () => {
      if (!userId || !briefingId) return;
      const sec = Math.floor((Date.now() - mountTime.current) / 1000);
      if (sec < 2) return; // ignore bounces
      engagement.mutate({
        user_id: userId,
        cluster_id: briefingId,
        action: "read",
        read_time_sec: sec,
      });
    };
  }, [userId, briefingId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Derive prev/next from cached list
  const cachedList = queryClient.getQueryData<Briefing[]>([
    "briefings",
    userId,
    "list",
    0,
  ]);
  let prevId: number | null = null;
  let nextId: number | null = null;
  if (cachedList && briefingId) {
    const idx = cachedList.findIndex((b) => b.id === briefingId);
    if (idx > 0) prevId = cachedList[idx - 1].id;
    if (idx >= 0 && idx < cachedList.length - 1)
      nextId = cachedList[idx + 1].id;
  }

  if (isLoading) {
    return (
      <main
        className="max-w-prose mx-auto px-4 py-8"
        data-testid="reader-loading"
      >
        <div className="space-y-4">
          <div className="h-4 w-24 bg-gray-100 animate-pulse rounded" />
          <div className="h-8 w-64 bg-gray-100 animate-pulse rounded" />
          <div className="h-96 w-full bg-gray-100 animate-pulse rounded" />
        </div>
      </main>
    );
  }

  if (error || !briefing) {
    return (
      <main
        className="max-w-prose mx-auto px-4 py-8"
        data-testid="reader-error"
      >
        <h1 className="text-xl font-bold text-gray-800 mb-2">
          Briefing not found
        </h1>
        <p className="text-gray-500 mb-4">
          This briefing may have been removed or is not yet available.
        </p>
        <a
          href="/briefings"
          className="text-sm text-violet-600 hover:underline"
        >
          Back to all briefings
        </a>
      </main>
    );
  }

  const hasHtml = !!briefing.content_html;
  const hasText = !!briefing.content_text;

  return (
    <main
      className="max-w-prose mx-auto px-4 py-8 space-y-8"
      data-testid="briefing-reader"
    >
      <ReaderHeader briefing={briefing} />

      {hasHtml ? (
        <HTMLRenderer html={briefing.content_html} />
      ) : hasText ? (
        <PlainTextRenderer text={briefing.content_text} />
      ) : (
        <p className="text-gray-400 text-sm" data-testid="no-content">
          This briefing has no content
        </p>
      )}

      <BriefingNav prevId={prevId} nextId={nextId} />
    </main>
  );
}
