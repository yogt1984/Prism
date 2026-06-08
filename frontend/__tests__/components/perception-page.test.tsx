import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createWrapper } from "../helpers/query-wrapper";
import { makeKeyword, makePerception, makePerceptionHistory } from "../helpers/fixtures";
import type { Keyword, PerceptionSnapshot } from "@/lib/types";

// --- mocks ---
const mockSession = vi.hoisted(() => ({
  data: { user: { id: 5, email: "u@test.com" } },
  status: "authenticated" as const,
}));

const mockRedirect = vi.hoisted(() => vi.fn());

vi.mock("next-auth/react", () => ({
  useSession: () => mockSession,
}));

vi.mock("next/navigation", () => ({
  redirect: mockRedirect,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
}));

// Mock recharts
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  ComposedChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="composed-chart">{children}</div>
  ),
  Line: () => <div data-testid="mock-line" />,
  Bar: () => <div data-testid="mock-bar" />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  ReferenceLine: () => <div />,
  CartesianGrid: () => <div />,
}));

const mockFetch = vi.hoisted(() => vi.fn());
vi.stubGlobal("fetch", mockFetch);

import PerceptionPage from "@/app/perception/page";

const keywords: Keyword[] = [
  makeKeyword({ id: 7, keyword: "tariffs", category: "finance" }),
  makeKeyword({
    id: 8,
    keyword: "AI regulation",
    category: "technology",
    aliases: "AI safety,AI governance",
  }),
  makeKeyword({ id: 9, keyword: "climate", category: "science" }),
];

function setupFetchResponses(opts: {
  keywords?: Keyword[];
  perception?: PerceptionSnapshot;
  history?: PerceptionSnapshot[];
  keywordError?: boolean;
} = {}) {
  const kws = opts.keywords ?? keywords;
  const perc = opts.perception ?? makePerception();
  const hist = opts.history ?? makePerceptionHistory(10);

  mockFetch.mockImplementation((url: string) => {
    if (opts.keywordError && url.includes("/keywords")) {
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: "Server error" }),
      });
    }
    if (url.includes("/keywords?active=true") || url.includes("/keywords%3Factive")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(kws),
      });
    }
    if (url.includes("/perception/history")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(hist),
      });
    }
    if (url.includes("/perception")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(perc),
      });
    }
    // POST /keywords (add)
    if (url.includes("/keywords") && !url.includes("?")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(makeKeyword({ id: 99, keyword: "new" })),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({}),
    });
  });
}

describe("PerceptionPage", () => {
  let Wrapper: ReturnType<typeof createWrapper>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSession.status = "authenticated";
    Wrapper = createWrapper();
  });

  it("redirects unauthenticated users", () => {
    mockSession.status = "unauthenticated";
    setupFetchResponses({ keywords: [] });
    render(<PerceptionPage />, { wrapper: Wrapper });
    expect(mockRedirect).toHaveBeenCalledWith("/auth/signin");
  });

  it("shows loading skeleton while keywords load", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<PerceptionPage />, { wrapper: Wrapper });
    expect(screen.getByTestId("loading-skeleton")).toBeInTheDocument();
  });

  it("renders page header", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    expect(screen.getByText("Perception Tracker")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Monitor how media frames your tracked topics over time",
      ),
    ).toBeInTheDocument();
  });

  it("shows error state on keyword fetch failure", async () => {
    setupFetchResponses({ keywordError: true });
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("error-state")).toBeInTheDocument();
    });
    expect(screen.getByText("Could not load keywords")).toBeInTheDocument();
    expect(screen.getByTestId("retry-btn")).toBeInTheDocument();
  });

  it("shows empty state when no keywords", async () => {
    setupFetchResponses({ keywords: [] });
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText("Start tracking a topic")).toBeInTheDocument();
    expect(screen.getByTestId("empty-add-btn")).toBeInTheDocument();
  });

  it("renders keyword cards for all keywords", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("keyword-card-7")).toBeInTheDocument();
      expect(screen.getByTestId("keyword-card-8")).toBeInTheDocument();
      expect(screen.getByTestId("keyword-card-9")).toBeInTheDocument();
    });
  });

  it("renders keyword grid", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("keyword-grid")).toBeInTheDocument();
    });
  });

  it("renders Add Keyword button", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("add-keyword-btn")).toBeInTheDocument();
    });
  });

  it("does not show Add Keyword button when empty", async () => {
    setupFetchResponses({ keywords: [] });
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("add-keyword-btn")).toBeNull();
  });

  it("opens modal on Add Keyword click", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("add-keyword-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("add-keyword-btn"));
    expect(screen.getByTestId("add-keyword-modal")).toBeInTheDocument();
  });

  it("opens modal from empty state button", async () => {
    setupFetchResponses({ keywords: [] });
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("empty-add-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("empty-add-btn"));
    expect(screen.getByTestId("add-keyword-modal")).toBeInTheDocument();
  });

  it("closes modal on close button click", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("add-keyword-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("add-keyword-btn"));
    expect(screen.getByTestId("add-keyword-modal")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("modal-close-btn"));
    expect(screen.queryByTestId("add-keyword-modal")).toBeNull();
  });

  it("opens detail panel when expand clicked", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("keyword-card-7")).toBeInTheDocument();
    });

    const expandBtns = screen.getAllByTestId("expand-btn");
    fireEvent.click(expandBtns[0]);

    await waitFor(() => {
      expect(screen.getByTestId("detail-panel")).toBeInTheDocument();
    });
    expect(screen.getByTestId("detail-keyword")).toHaveTextContent(
      "tariffs",
    );
  });

  it("closes detail panel on close click", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("keyword-card-7")).toBeInTheDocument();
    });

    // Open detail
    const expandBtns = screen.getAllByTestId("expand-btn");
    fireEvent.click(expandBtns[0]);

    await waitFor(() => {
      expect(screen.getByTestId("detail-panel")).toBeInTheDocument();
    });

    // Close detail
    fireEvent.click(screen.getByTestId("detail-close-btn"));
    expect(screen.queryByTestId("detail-panel")).toBeNull();
  });

  it("shows perception values on keyword cards", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const values = screen.getAllByTestId("perception-value");
      expect(values.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows momentum arrows on keyword cards", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const arrows = screen.getAllByTestId("momentum-arrow");
      expect(arrows.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows mini charts on keyword cards", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const charts = screen.getAllByTestId("mini-chart");
      expect(charts.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("retries on error state button click", async () => {
    setupFetchResponses({ keywordError: true });
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("error-state")).toBeInTheDocument();
    });

    // Fix fetch for retry
    setupFetchResponses();
    fireEvent.click(screen.getByTestId("retry-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("keyword-grid")).toBeInTheDocument();
    });
  });

  it("keyword names display correctly", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const names = screen.getAllByTestId("keyword-name");
      expect(names).toHaveLength(3);
      expect(names[0]).toHaveTextContent("tariffs");
      expect(names[1]).toHaveTextContent("AI regulation");
      expect(names[2]).toHaveTextContent("climate");
    });
  });

  it("detail panel shows time range selector", async () => {
    setupFetchResponses();
    render(<PerceptionPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("keyword-card-7")).toBeInTheDocument();
    });

    const expandBtns = screen.getAllByTestId("expand-btn");
    fireEvent.click(expandBtns[0]);

    await waitFor(() => {
      expect(screen.getByTestId("time-range-selector")).toBeInTheDocument();
    });
  });
});
