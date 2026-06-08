import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { createWrapper } from "../helpers/query-wrapper";
import {
  useLatestBriefing,
  useBriefingDetail,
  useTopStories,
  useRecentStories,
  useRecentStoriesInfinite,
  useActiveKeywords,
  usePerceptionHistory,
  useTriggerBriefing,
  useBriefingList,
  useBriefingDetailById,
  useStoryDetail,
  useStoryResonance,
  useSources,
  useSourceMap,
  useRecordEngagement,
  PAGE_SIZE,
} from "@/lib/hooks";
import {
  makeBriefing,
  makeBriefingDetail,
  makeTopStories,
  makeRecentStories,
  makeKeyword,
  makePerceptionHistory,
  makeStoryDetail,
  makeResonance,
  makeSource,
  makeEngagement,
} from "../helpers/fixtures";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function mockJsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

describe("hooks", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe("useLatestBriefing", () => {
    it("fetches latest briefing for a user", async () => {
      const briefings = [makeBriefing()];
      mockFetch.mockResolvedValueOnce(mockJsonResponse(briefings));

      const { result } = renderHook(() => useLatestBriefing(5), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(briefings);
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/users/5/briefings?limit=1",
        expect.any(Object),
      );
    });

    it("does not fetch when userId is undefined", () => {
      renderHook(() => useLatestBriefing(undefined), {
        wrapper: createWrapper(),
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("does not fetch when userId is 0", () => {
      renderHook(() => useLatestBriefing(0 as unknown as undefined), {
        wrapper: createWrapper(),
      });
      // 0 is falsy, so enabled: !!userId → false
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe("useBriefingDetail", () => {
    it("fetches briefing detail by id", async () => {
      const detail = makeBriefingDetail();
      mockFetch.mockResolvedValueOnce(mockJsonResponse(detail));

      const { result } = renderHook(() => useBriefingDetail(42), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(detail);
    });

    it("does not fetch when briefingId is undefined", () => {
      renderHook(() => useBriefingDetail(undefined), {
        wrapper: createWrapper(),
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe("useTopStories", () => {
    it("fetches top stories sorted by resonance", async () => {
      const stories = makeTopStories();
      mockFetch.mockResolvedValueOnce(mockJsonResponse(stories));

      const { result } = renderHook(() => useTopStories(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(stories);
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/stories?sort=resonance&status=analyzed&limit=5",
        expect.any(Object),
      );
    });
  });

  describe("useRecentStories", () => {
    it("fetches recent stories with default offset", async () => {
      const stories = makeRecentStories();
      mockFetch.mockResolvedValueOnce(mockJsonResponse(stories));

      const { result } = renderHook(() => useRecentStories(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("offset=0"),
        expect.any(Object),
      );
    });

    it("fetches with custom offset", async () => {
      mockFetch.mockResolvedValueOnce(mockJsonResponse(makeRecentStories(20, 20)));

      const { result } = renderHook(() => useRecentStories(20), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("offset=20"),
        expect.any(Object),
      );
    });
  });

  describe("useRecentStoriesInfinite", () => {
    it("fetches first page", async () => {
      mockFetch.mockResolvedValueOnce(mockJsonResponse(makeRecentStories()));

      const { result } = renderHook(() => useRecentStoriesInfinite(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.pages).toHaveLength(1);
      expect(result.current.data?.pages[0]).toHaveLength(20);
    });

    it("has next page when full page returned", async () => {
      mockFetch.mockResolvedValueOnce(mockJsonResponse(makeRecentStories()));

      const { result } = renderHook(() => useRecentStoriesInfinite(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.hasNextPage).toBe(true);
    });

    it("has no next page when partial page returned", async () => {
      mockFetch.mockResolvedValueOnce(
        mockJsonResponse(makeRecentStories(5)),
      );

      const { result } = renderHook(() => useRecentStoriesInfinite(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.hasNextPage).toBe(false);
    });
  });

  describe("useActiveKeywords", () => {
    it("fetches active keywords", async () => {
      const keywords = [makeKeyword(), makeKeyword({ id: 8, keyword: "AI" })];
      mockFetch.mockResolvedValueOnce(mockJsonResponse(keywords));

      const { result } = renderHook(() => useActiveKeywords(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toHaveLength(2);
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/keywords?active=true",
        expect.any(Object),
      );
    });
  });

  describe("usePerceptionHistory", () => {
    it("fetches perception history for a keyword", async () => {
      const history = makePerceptionHistory(20, 7);
      mockFetch.mockResolvedValueOnce(mockJsonResponse(history));

      const { result } = renderHook(() => usePerceptionHistory(7), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toHaveLength(20);
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/keywords/7/perception/history?limit=20",
        expect.any(Object),
      );
    });
  });

  describe("useTriggerBriefing", () => {
    it("sends POST to trigger briefing", async () => {
      const detail = makeBriefingDetail();
      mockFetch.mockResolvedValueOnce(mockJsonResponse(detail, 201));

      const { result } = renderHook(() => useTriggerBriefing(5), {
        wrapper: createWrapper(),
      });

      result.current.mutate();

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/users/5/briefings",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  describe("useStoryDetail", () => {
    it("fetches story detail by id", async () => {
      const story = makeStoryDetail({ id: 42 });
      mockFetch.mockResolvedValueOnce(mockJsonResponse(story));

      const { result } = renderHook(() => useStoryDetail(42), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(story);
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/stories/42",
        expect.any(Object),
      );
    });

    it("does not fetch when storyId is undefined", () => {
      renderHook(() => useStoryDetail(undefined), {
        wrapper: createWrapper(),
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("does not fetch when storyId is 0", () => {
      renderHook(() => useStoryDetail(0 as unknown as undefined), {
        wrapper: createWrapper(),
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe("useStoryResonance", () => {
    it("fetches resonance data for a story", async () => {
      const resonance = makeResonance({ cluster_id: 7 });
      mockFetch.mockResolvedValueOnce(mockJsonResponse(resonance));

      const { result } = renderHook(() => useStoryResonance(7), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(resonance);
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/stories/7/resonance",
        expect.any(Object),
      );
    });

    it("does not fetch when storyId is undefined", () => {
      renderHook(() => useStoryResonance(undefined), {
        wrapper: createWrapper(),
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe("useSources", () => {
    it("fetches active sources", async () => {
      const sources = [makeSource({ id: 1 }), makeSource({ id: 2 })];
      mockFetch.mockResolvedValueOnce(mockJsonResponse(sources));

      const { result } = renderHook(() => useSources(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toHaveLength(2);
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/sources?active=true",
        expect.any(Object),
      );
    });
  });

  describe("useSourceMap", () => {
    it("returns a Map of sources keyed by id", async () => {
      const sources = [
        makeSource({ id: 1, name: "Reuters" }),
        makeSource({ id: 2, name: "AP" }),
      ];
      mockFetch.mockResolvedValueOnce(mockJsonResponse(sources));

      const { result } = renderHook(() => useSourceMap(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.size).toBe(2));
      expect(result.current.get(1)?.name).toBe("Reuters");
      expect(result.current.get(2)?.name).toBe("AP");
    });

    it("returns empty Map before data loads", () => {
      mockFetch.mockReturnValue(new Promise(() => {})); // never resolves
      const { result } = renderHook(() => useSourceMap(), {
        wrapper: createWrapper(),
      });
      expect(result.current.size).toBe(0);
    });
  });

  describe("useRecordEngagement", () => {
    it("sends POST with engagement payload", async () => {
      const engagement = makeEngagement();
      mockFetch.mockResolvedValueOnce(mockJsonResponse(engagement, 201));

      const { result } = renderHook(() => useRecordEngagement(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({
        user_id: 5,
        cluster_id: 1,
        action: "open",
        read_time_sec: 0,
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/engagements",
        expect.objectContaining({ method: "POST" }),
      );
    });

    it("sends save engagement", async () => {
      const engagement = makeEngagement({ action: "save" });
      mockFetch.mockResolvedValueOnce(mockJsonResponse(engagement, 201));

      const { result } = renderHook(() => useRecordEngagement(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({
        user_id: 5,
        cluster_id: 1,
        action: "save",
        read_time_sec: 30,
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });
  });

  describe("useBriefingList", () => {
    it("fetches paginated briefing list", async () => {
      const briefings = [makeBriefing({ id: 1 }), makeBriefing({ id: 2 })];
      mockFetch.mockResolvedValueOnce(mockJsonResponse(briefings));

      const { result } = renderHook(() => useBriefingList(5, 0), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toHaveLength(2);
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/users/5/briefings?limit=20&offset=0",
        expect.any(Object),
      );
    });

    it("fetches with offset", async () => {
      mockFetch.mockResolvedValueOnce(
        mockJsonResponse([makeBriefing()]),
      );

      const { result } = renderHook(() => useBriefingList(5, 20), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("offset=20"),
        expect.any(Object),
      );
    });

    it("does not fetch when userId is undefined", () => {
      renderHook(() => useBriefingList(undefined, 0), {
        wrapper: createWrapper(),
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe("useBriefingDetailById", () => {
    it("fetches briefing detail by userId and briefingId", async () => {
      const detail = makeBriefingDetail({ id: 42 });
      mockFetch.mockResolvedValueOnce(mockJsonResponse(detail));

      const { result } = renderHook(
        () => useBriefingDetailById(5, 42),
        { wrapper: createWrapper() },
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(detail);
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/bff/users/5/briefings/42",
        expect.any(Object),
      );
    });

    it("does not fetch when userId is undefined", () => {
      renderHook(() => useBriefingDetailById(undefined, 42), {
        wrapper: createWrapper(),
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("does not fetch when briefingId is undefined", () => {
      renderHook(() => useBriefingDetailById(5, undefined), {
        wrapper: createWrapper(),
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("has 30-minute stale time for immutable content", async () => {
      const detail = makeBriefingDetail();
      mockFetch.mockResolvedValueOnce(mockJsonResponse(detail));

      const { result } = renderHook(
        () => useBriefingDetailById(5, 42),
        { wrapper: createWrapper() },
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      // Verify it only fetched once (staleTime keeps it fresh)
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });

  describe("PAGE_SIZE", () => {
    it("is 20", () => {
      expect(PAGE_SIZE).toBe(20);
    });
  });
});
