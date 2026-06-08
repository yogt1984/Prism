import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createWrapper } from "../helpers/query-wrapper";
import { makeKeyword, makePerception, makePerceptionHistory } from "../helpers/fixtures";

// Mock recharts
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  ComposedChart: ({ children, data }: { children: React.ReactNode; data: unknown[] }) => (
    <div data-testid="composed-chart" data-count={data.length}>
      {children}
    </div>
  ),
  Line: ({ dataKey }: { dataKey: string }) => (
    <div data-testid={`chart-line-${dataKey}`} />
  ),
  Bar: ({ dataKey }: { dataKey: string }) => (
    <div data-testid={`chart-bar-${dataKey}`} />
  ),
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  Tooltip: () => <div data-testid="tooltip" />,
  ReferenceLine: () => <div data-testid="reference-line" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
}));

const mockFetch = vi.hoisted(() => vi.fn());
vi.stubGlobal("fetch", mockFetch);

import DetailPanel from "@/components/perception/DetailPanel";

describe("DetailPanel", () => {
  let Wrapper: ReturnType<typeof createWrapper>;
  const keyword = makeKeyword({ aliases: "trade war,import duties" });
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    Wrapper = createWrapper();

    // Mock both latest perception and history endpoints
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/perception/history")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(makePerceptionHistory(10)),
        });
      }
      if (url.includes("/perception")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(makePerception()),
        });
      }
      return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ detail: "Not found" }),
      });
    });
  });

  it("renders keyword name", async () => {
    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    expect(screen.getByTestId("detail-keyword")).toHaveTextContent(
      "tariffs",
    );
  });

  it("renders aliases", async () => {
    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    expect(screen.getByTestId("detail-aliases")).toHaveTextContent(
      "Also: trade war, import duties",
    );
  });

  it("does not render aliases when empty", async () => {
    const kw = makeKeyword({ aliases: "" });
    render(<DetailPanel keyword={kw} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    expect(screen.queryByTestId("detail-aliases")).toBeNull();
  });

  it("renders time range selector", async () => {
    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    expect(screen.getByTestId("time-range-selector")).toBeInTheDocument();
  });

  it("defaults to 7d time range", async () => {
    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    expect(screen.getByTestId("time-range-7d")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("renders chart after data loads", async () => {
    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    await waitFor(() => {
      expect(screen.getByTestId("perception-chart")).toBeInTheDocument();
    });
  });

  it("renders momentum indicator after latest loads", async () => {
    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    await waitFor(() => {
      expect(screen.getByTestId("momentum-indicator")).toBeInTheDocument();
    });
  });

  it("calls onClose when close button clicked", async () => {
    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    fireEvent.click(screen.getByTestId("detail-close-btn"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("changes time range on selector click", async () => {
    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    fireEvent.click(screen.getByTestId("time-range-24h"));
    expect(screen.getByTestId("time-range-24h")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("time-range-7d")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("shows error state on history fetch failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/perception/history")) {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: "Server error" }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(makePerception()),
      });
    });

    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    await waitFor(() => {
      expect(screen.getByTestId("chart-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Could not load history")).toBeInTheDocument();
    expect(screen.getByTestId("chart-retry-btn")).toBeInTheDocument();
  });

  it("has detail-panel test id", async () => {
    render(<DetailPanel keyword={keyword} onClose={onClose} />, {
      wrapper: Wrapper,
    });
    expect(screen.getByTestId("detail-panel")).toBeInTheDocument();
  });
});
