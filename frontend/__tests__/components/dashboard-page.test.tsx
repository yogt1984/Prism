import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "@/app/dashboard/page";
import {
  makeBriefing,
  makeBriefingDetail,
  makeTopStories,
  makeRecentStories,
} from "../helpers/fixtures";

const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

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

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockUseSession.mockReturnValue({
      data: {
        user: { id: 5, name: "Alice", email: "alice@example.com", isPro: false, interests: "finance" },
      },
    });
  });

  it("renders dashboard with all sections", async () => {
    const briefing = makeBriefing();
    const detail = makeBriefingDetail();
    const topStories = makeTopStories();
    const recentStories = makeRecentStories(5);

    // Route responses based on URL
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("/briefings?limit=1")) return mockJsonResponse([briefing]);
      if (url.includes(`/briefings/${briefing.id}`)) return mockJsonResponse(detail);
      if (url.includes("sort=resonance")) return mockJsonResponse(topStories);
      if (url.includes("sort=first_seen")) return mockJsonResponse(recentStories);
      if (url.includes("/keywords")) return mockJsonResponse([]);
      return mockJsonResponse([]);
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Today's Briefing")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("Top Stories")).toBeInTheDocument();
    });

    expect(screen.getByText("Recent Stories")).toBeInTheDocument();
  });

  it("renders sidebar with user greeting", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse([]));
    renderPage();

    expect(screen.getByTestId("user-greeting")).toHaveTextContent("Alice");
  });

  it("shows briefing card with story count", async () => {
    const briefing = makeBriefing({ story_count: 12 });
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("/briefings?limit=1")) return mockJsonResponse([briefing]);
      if (url.includes(`/briefings/${briefing.id}`)) return mockJsonResponse(makeBriefingDetail());
      return mockJsonResponse([]);
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("12 stories")).toBeInTheDocument();
    });
  });

  it("shows empty briefing state for new user", async () => {
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("/briefings?limit=1")) return mockJsonResponse([]);
      return mockJsonResponse([]);
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("briefing-empty")).toBeInTheDocument();
    });
  });

  it("shows top stories section with cards", async () => {
    const topStories = makeTopStories(3);
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("sort=resonance")) return mockJsonResponse(topStories);
      if (url.includes("/briefings?limit=1")) return mockJsonResponse([]);
      return mockJsonResponse([]);
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getAllByTestId("story-card")).toHaveLength(3);
    });
  });

  it("shows recent stories feed", async () => {
    const recent = makeRecentStories(10);
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("sort=first_seen")) return mockJsonResponse(recent);
      if (url.includes("/briefings?limit=1")) return mockJsonResponse([]);
      if (url.includes("sort=resonance")) return mockJsonResponse([]);
      return mockJsonResponse([]);
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getAllByTestId("story-row")).toHaveLength(10);
    });
  });

  it("renders empty states for all sections when no data", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse([]));

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("briefing-empty")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByTestId("stories-empty")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByTestId("recent-empty")).toBeInTheDocument();
    });
  });

  it("does not fetch briefings when no userId in session", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Guest", email: "guest@example.com" } },
    });
    mockFetch.mockResolvedValue(mockJsonResponse([]));

    renderPage();

    // Should not have called briefings endpoint (no userId)
    const briefingCalls = mockFetch.mock.calls.filter(
      (call: string[]) => call[0].includes("/briefings?limit=1"),
    );
    expect(briefingCalls).toHaveLength(0);
  });
});
