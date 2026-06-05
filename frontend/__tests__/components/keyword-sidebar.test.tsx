import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import KeywordSidebar from "@/components/dashboard/KeywordSidebar";
import { makeKeyword, makePerceptionHistory } from "../helpers/fixtures";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function mockJsonResponse(data: unknown) {
  return { ok: true, status: 200, json: async () => data };
}

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("KeywordSidebar", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("shows loading skeleton while fetching", () => {
    mockFetch.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithQuery(<KeywordSidebar />);
    expect(screen.getByTestId("keywords-skeleton")).toBeInTheDocument();
  });

  it("shows empty state when no keywords", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse([]));
    renderWithQuery(<KeywordSidebar />);

    await waitFor(() => {
      expect(screen.getByTestId("keywords-empty")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Track your first keyword/),
    ).toBeInTheDocument();
  });

  it("shows Add keyword button in empty state", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse([]));
    renderWithQuery(<KeywordSidebar />);

    await waitFor(() => {
      expect(screen.getByText("+ Add keyword")).toBeInTheDocument();
    });
  });

  it("renders keyword items when data is available", async () => {
    const keywords = [
      makeKeyword({ id: 7, keyword: "tariffs" }),
      makeKeyword({ id: 8, keyword: "AI regulation" }),
    ];
    // First call: keywords, subsequent calls: perception histories
    mockFetch
      .mockResolvedValueOnce(mockJsonResponse(keywords))
      .mockResolvedValue(mockJsonResponse(makePerceptionHistory(5)));

    renderWithQuery(<KeywordSidebar />);

    await waitFor(() => {
      expect(screen.getByText("tariffs")).toBeInTheDocument();
      expect(screen.getByText("AI regulation")).toBeInTheDocument();
    });
  });

  it("renders Tracked Keywords heading", async () => {
    mockFetch
      .mockResolvedValueOnce(
        mockJsonResponse([makeKeyword()]),
      )
      .mockResolvedValue(mockJsonResponse(makePerceptionHistory(5)));

    renderWithQuery(<KeywordSidebar />);

    await waitFor(() => {
      expect(screen.getByText("Tracked Keywords")).toBeInTheDocument();
    });
  });

  it("renders sparklines for each keyword", async () => {
    mockFetch
      .mockResolvedValueOnce(
        mockJsonResponse([makeKeyword()]),
      )
      .mockResolvedValue(mockJsonResponse(makePerceptionHistory(10)));

    renderWithQuery(<KeywordSidebar />);

    await waitFor(() => {
      expect(
        screen.getByRole("img", { name: "Perception sparkline" }),
      ).toBeInTheDocument();
    });
  });
});
