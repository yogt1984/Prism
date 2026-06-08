"use client";

import { useParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useEffect, useRef } from "react";
import StoryHeader from "@/components/story/StoryHeader";
import NeutralSummary from "@/components/story/NeutralSummary";
import ResonancePanel from "@/components/story/ResonancePanel";
import PerspectiveViewer from "@/components/story/PerspectiveViewer";
import ArticleSourcesList from "@/components/story/ArticleSourcesList";
import EngagementBar from "@/components/story/EngagementBar";
import {
  useStoryDetail,
  useStoryResonance,
  useSourceMap,
  useRecordEngagement,
} from "@/lib/hooks";

export default function StoryDetailPage() {
  const params = useParams();
  const storyId = params?.id ? Number(params.id) : undefined;
  const { data: session } = useSession();
  const userId = (session?.user as Record<string, unknown> | undefined)
    ?.id as number | undefined;

  const { data: story, isLoading, error } = useStoryDetail(storyId);
  const { data: resonance, isLoading: resonanceLoading } =
    useStoryResonance(storyId);
  const sourceMap = useSourceMap();
  const engagement = useRecordEngagement();

  const openRecorded = useRef(false);

  useEffect(() => {
    if (userId && storyId && !openRecorded.current) {
      openRecorded.current = true;
      engagement.mutate({
        user_id: userId,
        cluster_id: storyId,
        action: "open",
        read_time_sec: 0,
      });
    }
  }, [userId, storyId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8" data-testid="story-loading">
        <div className="space-y-4">
          <div className="h-6 w-48 bg-gray-100 animate-pulse rounded" />
          <div className="h-10 w-full bg-gray-100 animate-pulse rounded" />
          <div className="h-24 w-full bg-gray-100 animate-pulse rounded" />
        </div>
      </main>
    );
  }

  if (error || !story) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8" data-testid="story-error">
        <h1 className="text-xl font-bold text-gray-800 mb-2">Story not found</h1>
        <p className="text-gray-500">
          This story may have been removed or is not yet available.
        </p>
      </main>
    );
  }

  const handleEngage = (action: "save" | "skip", readTimeSec: number) => {
    if (!userId || !storyId) return;
    engagement.mutate({
      user_id: userId,
      cluster_id: storyId,
      action,
      read_time_sec: readTimeSec,
    });
  };

  return (
    <main className="max-w-4xl mx-auto px-4 py-8 space-y-8" data-testid="story-detail">
      <StoryHeader story={story} />
      <NeutralSummary text={story.summary} />
      <ResonancePanel resonance={resonance ?? null} isLoading={resonanceLoading} />
      <PerspectiveViewer
        perspectives={story.perspectives}
        sourceMap={sourceMap}
      />
      <ArticleSourcesList articles={story.articles} sourceMap={sourceMap} />
      <EngagementBar
        onEngage={handleEngage}
        isPending={engagement.isPending}
        storyUrl={`/stories/${storyId}`}
      />
    </main>
  );
}
