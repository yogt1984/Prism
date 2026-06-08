import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createWrapper } from "../helpers/query-wrapper";
import { makeSourceList, makeSource } from "../helpers/fixtures";
import type { Source } from "@/lib/types";

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

const mockFetch = vi.hoisted(() => vi.fn());
vi.stubGlobal("fetch", mockFetch);

function respondWithSources(sources: Source[]) {
  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(sources),
  });
}

function respondWithError() {
  mockFetch.mockResolvedValue({
    ok: false,
    status: 500,
    json: () => Promise.resolve({ detail: "Server error" }),
  });
}

import SourcesPage, {
  filterSources,
  BIAS_ORDER,
  BIAS_CHIPS,
} from "@/app/sources/page";

describe("filterSources", () => {
  const sources = makeSourceList();

  it("returns all sources with no filters", () => {
    const result = filterSources(sources, "", null, "trust_desc");
    expect(result).toHaveLength(10);
  });

  it("filters by name search (case insensitive)", () => {
    const result = filterSources(sources, "reuters", null, "trust_desc");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Reuters");
  });

  it("filters by URL search", () => {
    const result = filterSources(sources, "bbc.com", null, "trust_desc");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("BBC");
  });

  it("filters by bias label", () => {
    const result = filterSources(sources, "", "center_left", "trust_desc");
    expect(result).toHaveLength(3); // BBC, CNN, NPR
    result.forEach((s) => expect(s.bias_label).toBe("center_left"));
  });

  it("combines search and bias filter", () => {
    const result = filterSources(sources, "bbc", "center_left", "trust_desc");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("BBC");
  });

  it("sorts by trust_desc", () => {
    const result = filterSources(sources, "", null, "trust_desc");
    for (let i = 1; i < result.length; i++) {
      expect(result[i - 1].trust_score).toBeGreaterThanOrEqual(
        result[i].trust_score,
      );
    }
  });

  it("sorts by trust_asc", () => {
    const result = filterSources(sources, "", null, "trust_asc");
    for (let i = 1; i < result.length; i++) {
      expect(result[i - 1].trust_score).toBeLessThanOrEqual(
        result[i].trust_score,
      );
    }
  });

  it("sorts by name_asc", () => {
    const result = filterSources(sources, "", null, "name_asc");
    for (let i = 1; i < result.length; i++) {
      expect(result[i - 1].name.localeCompare(result[i].name)).toBeLessThanOrEqual(0);
    }
  });

  it("sorts by bias order (left to right)", () => {
    const result = filterSources(sources, "", null, "bias");
    for (let i = 1; i < result.length; i++) {
      expect(
        (BIAS_ORDER[result[i - 1].bias_label] ?? 5),
      ).toBeLessThanOrEqual(BIAS_ORDER[result[i].bias_label] ?? 5);
    }
  });

  it("returns empty array when search matches nothing", () => {
    const result = filterSources(sources, "nonexistent", null, "trust_desc");
    expect(result).toHaveLength(0);
  });

  it("returns empty array when bias filter matches nothing", () => {
    const result = filterSources(sources, "", "unknown", "trust_desc");
    expect(result).toHaveLength(0);
  });
});

describe("BIAS_ORDER", () => {
  it("has correct ordering", () => {
    expect(BIAS_ORDER.left).toBe(0);
    expect(BIAS_ORDER.center_left).toBe(1);
    expect(BIAS_ORDER.center).toBe(2);
    expect(BIAS_ORDER.center_right).toBe(3);
    expect(BIAS_ORDER.right).toBe(4);
    expect(BIAS_ORDER.unknown).toBe(5);
  });
});

describe("BIAS_CHIPS", () => {
  it("has 6 chips including All", () => {
    expect(BIAS_CHIPS).toHaveLength(6);
    expect(BIAS_CHIPS[0].value).toBeNull();
    expect(BIAS_CHIPS[0].label).toBe("All");
  });

  it("has colors for non-All chips", () => {
    BIAS_CHIPS.slice(1).forEach((chip) => {
      expect(chip.color).toBeDefined();
    });
  });
});

describe("SourcesPage", () => {
  let Wrapper: ReturnType<typeof createWrapper>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSession.status = "authenticated";
    Wrapper = createWrapper();
  });

  it("redirects unauthenticated users", () => {
    mockSession.status = "unauthenticated";
    respondWithSources([]);
    render(<SourcesPage />, { wrapper: Wrapper });
    expect(mockRedirect).toHaveBeenCalledWith("/auth/signin");
  });

  it("shows loading skeleton while fetching", () => {
    mockFetch.mockReturnValue(new Promise(() => {})); // never resolves
    render(<SourcesPage />, { wrapper: Wrapper });
    expect(screen.getByTestId("loading-skeleton")).toBeInTheDocument();
  });

  it("shows error state on fetch failure", async () => {
    respondWithError();
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("error-state")).toBeInTheDocument();
    });
    expect(screen.getByText("Could not load sources")).toBeInTheDocument();
    expect(screen.getByTestId("retry-btn")).toBeInTheDocument();
  });

  it("renders page header", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByText("News Sources")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        "Every source Prism aggregates from, with trust and bias ratings",
      ),
    ).toBeInTheDocument();
  });

  it("shows source count", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("source-count")).toHaveTextContent(
        "10 active sources",
      );
    });
  });

  it("renders all sources in table", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    const rows = screen.getAllByTestId("source-row");
    expect(rows).toHaveLength(10);
  });

  it("renders search input", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("search-input")).toBeInTheDocument();
    });
    expect(screen.getByPlaceholderText("Search sources...")).toBeInTheDocument();
  });

  it("renders sort select with 4 options", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("sort-select")).toBeInTheDocument();
    });
    const options = screen.getByTestId("sort-select").querySelectorAll("option");
    expect(options).toHaveLength(4);
  });

  it("renders bias filter chips", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("bias-filters")).toBeInTheDocument();
    });
    expect(screen.getByTestId("filter-chip-all")).toBeInTheDocument();
    expect(screen.getByTestId("filter-chip-left")).toBeInTheDocument();
    expect(screen.getByTestId("filter-chip-center")).toBeInTheDocument();
    expect(screen.getByTestId("filter-chip-right")).toBeInTheDocument();
  });

  it("filters sources by search input", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "reuters" },
    });

    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(1);
    });
  });

  it("shows empty search state", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "zzzzz" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("empty-search")).toBeInTheDocument();
    });
    expect(screen.getByTestId("clear-search-btn")).toBeInTheDocument();
  });

  it("clears search when Clear button clicked", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "zzzzz" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("empty-search")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("clear-search-btn"));

    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });
  });

  it("filters by bias chip", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.click(screen.getByTestId("filter-chip-right"));

    await waitFor(() => {
      const rows = screen.getAllByTestId("source-row");
      expect(rows).toHaveLength(2); // Fox News + Breitbart
    });
  });

  it("shows empty bias state when no matches", async () => {
    respondWithSources([
      makeSource({ id: 1, bias_label: "center" }),
    ]);
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(1);
    });

    fireEvent.click(screen.getByTestId("filter-chip-left"));

    await waitFor(() => {
      expect(screen.getByTestId("empty-bias")).toBeInTheDocument();
    });
    expect(screen.getByTestId("reset-bias-btn")).toBeInTheDocument();
  });

  it("resets bias filter when Reset button clicked", async () => {
    respondWithSources([
      makeSource({ id: 1, bias_label: "center" }),
    ]);
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(1);
    });

    fireEvent.click(screen.getByTestId("filter-chip-left"));
    await waitFor(() => {
      expect(screen.getByTestId("empty-bias")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("reset-bias-btn"));

    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(1);
    });
  });

  it("changes sort mode via select", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.change(screen.getByTestId("sort-select"), {
      target: { value: "name_asc" },
    });

    await waitFor(() => {
      const rows = screen.getAllByTestId("source-row");
      // First alphabetically is "AP News"
      expect(rows[0]).toHaveTextContent("AP News");
    });
  });

  it("sorts by trust ascending", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.change(screen.getByTestId("sort-select"), {
      target: { value: "trust_asc" },
    });

    await waitFor(() => {
      const rows = screen.getAllByTestId("source-row");
      // Lowest trust is Breitbart (0.25)
      expect(rows[0]).toHaveTextContent("Breitbart");
    });
  });

  it("sorts by bias left to right", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.change(screen.getByTestId("sort-select"), {
      target: { value: "bias" },
    });

    await waitFor(() => {
      const rows = screen.getAllByTestId("source-row");
      // First should be "left" bias sources (Guardian, Jacobin)
      expect(rows[0]).toHaveTextContent(/Guardian|Jacobin/);
    });
  });

  it("renders source stats section", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("source-stats")).toBeInTheDocument();
    });
  });

  it("shows trust bars for each source (table + cards)", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      // jsdom renders both desktop table and mobile cards = 2x
      const bars = screen.getAllByTestId("trust-bar");
      expect(bars).toHaveLength(20);
    });
  });

  it("shows bias labels for each source (table + cards)", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const labels = screen.getAllByTestId("bias-label");
      expect(labels).toHaveLength(20);
    });
  });

  it("renders filter bar section", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("filter-bar")).toBeInTheDocument();
    });
  });

  it("singular 'source' for count 1", async () => {
    respondWithSources([makeSource({ id: 1 })]);
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("source-count")).toHaveTextContent(
        "1 active source",
      );
    });
  });

  it("renders View links for all sources (table + cards)", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      // jsdom renders both desktop table and mobile cards = 2x
      const links = screen.getAllByTestId("stories-link");
      expect(links).toHaveLength(20);
    });
  });

  it("retries on error state button click", async () => {
    respondWithError();
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("error-state")).toBeInTheDocument();
    });

    respondWithSources(makeSourceList());
    fireEvent.click(screen.getByTestId("retry-btn"));

    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });
  });

  it("search filters by URL substring", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "foxnews.com" },
    });

    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(1);
    });
  });

  it("search is case-insensitive", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "REUTERS" },
    });

    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(1);
    });
  });

  it("All chip is active by default", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("filter-chip-all")).toHaveAttribute(
        "aria-pressed",
        "true",
      );
    });
  });

  it("clicking bias chip deactivates All chip", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("filter-chip-all")).toHaveAttribute(
        "aria-pressed",
        "true",
      );
    });

    fireEvent.click(screen.getByTestId("filter-chip-left"));

    expect(screen.getByTestId("filter-chip-all")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("filter-chip-left")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("clicking All chip resets bias filter", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    fireEvent.click(screen.getByTestId("filter-chip-right"));
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(2);
    });

    fireEvent.click(screen.getByTestId("filter-chip-all"));
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });
  });

  it("combined search + bias + sort works together", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(10);
    });

    // Filter by center_left bias
    fireEvent.click(screen.getByTestId("filter-chip-center-left"));
    await waitFor(() => {
      expect(screen.getAllByTestId("source-row")).toHaveLength(3);
    });

    // Sort by name ascending
    fireEvent.change(screen.getByTestId("sort-select"), {
      target: { value: "name_asc" },
    });

    // BBC, CNN, NPR in alphabetical order
    await waitFor(() => {
      const rows = screen.getAllByTestId("source-row");
      expect(rows[0]).toHaveTextContent("BBC");
      expect(rows[1]).toHaveTextContent("CNN");
      expect(rows[2]).toHaveTextContent("NPR");
    });
  });

  it("default sort is trust descending", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const rows = screen.getAllByTestId("source-row");
      // Highest trust: Reuters (0.92)
      expect(rows[0]).toHaveTextContent("Reuters");
    });
  });

  it("renders table headers", async () => {
    respondWithSources(makeSourceList());
    render(<SourcesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByText("Source")).toBeInTheDocument();
      expect(screen.getByText("Trust Score")).toBeInTheDocument();
      expect(screen.getByText("Bias")).toBeInTheDocument();
      expect(screen.getByText("Stories")).toBeInTheDocument();
    });
  });
});
