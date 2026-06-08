import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { apiFetch } from "./api";
import type {
  Briefing,
  BriefingDetail,
  Engagement,
  Resonance,
  Source,
  Story,
  StoryDetail,
  User,
  Keyword,
  PerceptionSnapshot,
} from "./types";

const PAGE_SIZE = 20;

export function useLatestBriefing(userId: number | undefined) {
  return useQuery({
    queryKey: ["briefings", userId, "latest"],
    queryFn: () =>
      apiFetch<Briefing[]>(`/users/${userId}/briefings?limit=1`),
    enabled: !!userId,
    staleTime: 5 * 60_000,
  });
}

export function useBriefingDetail(briefingId: number | undefined) {
  return useQuery({
    queryKey: ["briefings", briefingId],
    queryFn: () =>
      apiFetch<BriefingDetail>(
        `/users/me/briefings/${briefingId}`,
      ),
    enabled: !!briefingId,
    staleTime: 5 * 60_000,
  });
}

export function useTopStories() {
  return useQuery({
    queryKey: ["stories", "top-resonance"],
    queryFn: () =>
      apiFetch<Story[]>("/stories?sort=resonance&status=analyzed&limit=5"),
    staleTime: 2 * 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useRecentStories(offset: number = 0) {
  return useQuery({
    queryKey: ["stories", "recent", offset],
    queryFn: () =>
      apiFetch<Story[]>(
        `/stories?sort=first_seen&status=analyzed&limit=${PAGE_SIZE}&offset=${offset}`,
      ),
    staleTime: 60_000,
  });
}

export function useRecentStoriesInfinite() {
  return useInfiniteQuery({
    queryKey: ["stories", "recent-infinite"],
    queryFn: ({ pageParam = 0 }) =>
      apiFetch<Story[]>(
        `/stories?sort=first_seen&status=analyzed&limit=${PAGE_SIZE}&offset=${pageParam}`,
      ),
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length >= PAGE_SIZE
        ? allPages.length * PAGE_SIZE
        : undefined,
    initialPageParam: 0,
    staleTime: 60_000,
  });
}

export function useActiveKeywords() {
  return useQuery({
    queryKey: ["keywords", "active"],
    queryFn: () => apiFetch<Keyword[]>("/keywords?active=true"),
    staleTime: 5 * 60_000,
  });
}

export function usePerceptionHistory(keywordId: number) {
  return useQuery({
    queryKey: ["perception", keywordId, "sparkline"],
    queryFn: () =>
      apiFetch<PerceptionSnapshot[]>(
        `/keywords/${keywordId}/perception/history?limit=20`,
      ),
    staleTime: 2 * 60_000,
  });
}

export function useStoryDetail(storyId: number | undefined) {
  return useQuery({
    queryKey: ["stories", storyId, "detail"],
    queryFn: () => apiFetch<StoryDetail>(`/stories/${storyId}`),
    enabled: !!storyId,
    staleTime: 5 * 60_000,
  });
}

export function useStoryResonance(storyId: number | undefined) {
  return useQuery({
    queryKey: ["stories", storyId, "resonance"],
    queryFn: () => apiFetch<Resonance>(`/stories/${storyId}/resonance`),
    enabled: !!storyId,
    staleTime: 5 * 60_000,
  });
}

export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: () => apiFetch<Source[]>("/sources?active=true"),
    staleTime: 30 * 60_000,
  });
}

export function useSourceMap() {
  const { data: sources = [] } = useSources();
  return new Map(sources.map((s) => [s.id, s]));
}

export function useRecordEngagement() {
  return useMutation({
    mutationKey: ["engagements"],
    mutationFn: (payload: {
      user_id: number;
      cluster_id: number;
      action: "open" | "read" | "save" | "skip";
      read_time_sec: number;
    }) =>
      apiFetch<Engagement>("/engagements", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useBriefingList(
  userId: number | undefined,
  offset: number = 0,
) {
  return useQuery({
    queryKey: ["briefings", userId, "list", offset],
    queryFn: () =>
      apiFetch<Briefing[]>(
        `/users/${userId}/briefings?limit=${PAGE_SIZE}&offset=${offset}`,
      ),
    enabled: !!userId,
    staleTime: 5 * 60_000,
  });
}

export function useBriefingDetailById(
  userId: number | undefined,
  briefingId: number | undefined,
) {
  return useQuery({
    queryKey: ["briefings", userId, briefingId],
    queryFn: () =>
      apiFetch<BriefingDetail>(
        `/users/${userId}/briefings/${briefingId}`,
      ),
    enabled: !!userId && !!briefingId,
    staleTime: 30 * 60_000,
  });
}

export function useUserProfile(userId: number | undefined) {
  return useQuery({
    queryKey: ["users", userId],
    queryFn: () => apiFetch<User>(`/users/${userId}`),
    enabled: !!userId,
    staleTime: 10 * 60_000,
  });
}

export function useUpdateUser(userId: number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: ["users", userId, "update"],
    mutationFn: (payload: Partial<User>) =>
      apiFetch<User>(`/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["users", userId], data);
    },
  });
}

export function useTriggerBriefing(userId: number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: ["briefings", "trigger"],
    mutationFn: () =>
      apiFetch<BriefingDetail>(`/users/${userId}/briefings`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["briefings", userId, "latest"],
      });
      queryClient.invalidateQueries({
        queryKey: ["briefings", userId, "list"],
      });
    },
  });
}

export { PAGE_SIZE };
