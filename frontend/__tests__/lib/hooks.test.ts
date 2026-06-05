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
  PAGE_SIZE,
} from "@/lib/hooks";
import {
  makeBriefing,
  makeBriefingDetail,
  makeTopStories,
  makeRecentStories,
  makeKeyword,
  makePerceptionHistory,
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

  describe("PAGE_SIZE", () => {
    it("is 20", () => {
      expect(PAGE_SIZE).toBe(20);
    });
  });
});
