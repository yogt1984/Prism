"use client";

import { useSession } from "next-auth/react";
import DashboardLayout from "@/components/dashboard/DashboardLayout";
import TodayBriefingCard from "@/components/dashboard/TodayBriefingCard";
import TopStoriesSection from "@/components/dashboard/TopStoriesSection";
import RecentStoriesFeed from "@/components/dashboard/RecentStoriesFeed";
import {
  useLatestBriefing,
  useBriefingDetail,
  useTopStories,
  useTriggerBriefing,
} from "@/lib/hooks";

export default function DashboardPage() {
  const { data: session } = useSession();
  const userId = (session?.user as Record<string, unknown> | undefined)
    ?.id as number | undefined;

  const { data: briefings = [], isLoading: briefingLoading } =
    useLatestBriefing(userId);
  const latestBriefing = briefings[0] ?? null;
  const { data: briefingDetail } = useBriefingDetail(latestBriefing?.id);

  const { data: topStories = [], isLoading: storiesLoading } = useTopStories();

  const triggerMutation = useTriggerBriefing(userId);

  return (
    <DashboardLayout
      onTriggerBriefing={() => triggerMutation.mutate()}
      isTriggerPending={triggerMutation.isPending}
    >
      <div className="space-y-8 max-w-4xl">
        <TodayBriefingCard
          briefing={latestBriefing}
          detail={briefingDetail}
          isLoading={briefingLoading}
          onTrigger={() => triggerMutation.mutate()}
          isTriggerPending={triggerMutation.isPending}
        />
        <TopStoriesSection stories={topStories} isLoading={storiesLoading} />
        <RecentStoriesFeed />
      </div>
    </DashboardLayout>
  );
}
