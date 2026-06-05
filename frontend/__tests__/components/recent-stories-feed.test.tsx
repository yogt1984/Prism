import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RecentStoriesFeed from "@/components/dashboard/RecentStoriesFeed";
import { makeRecentStories } from "../helpers/fixtures";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

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

describe("RecentStoriesFeed", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("shows loading skeleton while fetching", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<RecentStoriesFeed />);
    expect(screen.getByTestId("recent-skeleton")).toBeInTheDocument();
  });

  it("shows loading skeleton with 10 items", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<RecentStoriesFeed />);
    expect(
      screen.getByTestId("recent-skeleton").children,
    ).toHaveLength(10);
  });

  it("shows empty state when no stories", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse([]));
    renderWithQuery(<RecentStoriesFeed />);

    await waitFor(() => {
      expect(screen.getByTestId("recent-empty")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/No stories discovered yet/),
    ).toBeInTheDocument();
  });

  it("mentions pipeline schedule in empty state", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse([]));
    renderWithQuery(<RecentStoriesFeed />);

    await waitFor(() => {
      expect(
        screen.getByText(/pipeline runs every 2 hours/),
      ).toBeInTheDocument();
    });
  });

  it("renders story rows when data is available", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse(makeRecentStories(5)));
    renderWithQuery(<RecentStoriesFeed />);

    await waitFor(() => {
      expect(screen.getAllByTestId("story-row")).toHaveLength(5);
    });
  });

  it("renders section heading", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse(makeRecentStories(5)));
    renderWithQuery(<RecentStoriesFeed />);

    await waitFor(() => {
      expect(screen.getByText("Recent Stories")).toBeInTheDocument();
    });
  });

  it("shows Load more button when full page returned", async () => {
    mockFetch.mockResolvedValueOnce(
      mockJsonResponse(makeRecentStories(20)),
    );
    renderWithQuery(<RecentStoriesFeed />);

    await waitFor(() => {
      expect(screen.getByTestId("load-more")).toBeInTheDocument();
    });
  });

  it("hides Load more button when partial page returned", async () => {
    mockFetch.mockResolvedValueOnce(
      mockJsonResponse(makeRecentStories(10)),
    );
    renderWithQuery(<RecentStoriesFeed />);

    await waitFor(() => {
      expect(screen.getAllByTestId("story-row")).toHaveLength(10);
    });
    expect(screen.queryByTestId("load-more")).toBeNull();
  });

  it("fetches next page on Load more click", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce(
      mockJsonResponse(makeRecentStories(20, 0)),
    );
    renderWithQuery(<RecentStoriesFeed />);

    await waitFor(() => {
      expect(screen.getByTestId("load-more")).toBeInTheDocument();
    });

    // Mock second page
    mockFetch.mockResolvedValueOnce(
      mockJsonResponse(makeRecentStories(20, 20)),
    );
    await user.click(screen.getByTestId("load-more"));

    await waitFor(() => {
      // Should now have stories from both pages
      expect(screen.getAllByTestId("story-row")).toHaveLength(40);
    });
  });

  it("shows all accumulated stories after loading more", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce(
      mockJsonResponse(makeRecentStories(20, 0)),
    );
    renderWithQuery(<RecentStoriesFeed />);

    await waitFor(() => {
      expect(screen.getByTestId("load-more")).toBeInTheDocument();
    });

    // Second page with fewer items — no more pages
    mockFetch.mockResolvedValueOnce(
      mockJsonResponse(makeRecentStories(5, 20)),
    );
    await user.click(screen.getByTestId("load-more"));

    await waitFor(() => {
      expect(screen.getAllByTestId("story-row")).toHaveLength(25);
    });
    // Load more should disappear since last page was partial
    expect(screen.queryByTestId("load-more")).toBeNull();
  });
});
