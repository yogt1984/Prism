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
  Story,
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
    },
  });
}

export { PAGE_SIZE };
