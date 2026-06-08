import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { makeKeyword, makePerception, makePerceptionHistory } from "../helpers/fixtures";

// Mock recharts for MiniChart
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Line: () => <div data-testid="line" />,
  ReferenceLine: () => <div data-testid="reference-line" />,
}));

import KeywordOverviewCard from "@/components/perception/KeywordOverviewCard";

const baseProps = {
  keyword: makeKeyword(),
  latest: makePerception(),
  history: makePerceptionHistory(10),
  isHistoryLoading: false,
  onExpand: vi.fn(),
  onRemove: vi.fn(),
};

describe("KeywordOverviewCard", () => {
  it("renders keyword name", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByTestId("keyword-name")).toHaveTextContent("tariffs");
  });

  it("renders category badge", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByText("finance")).toBeInTheDocument();
  });

  it("renders perception value when latest exists", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByTestId("perception-value")).toHaveTextContent(
      "-0.35",
    );
  });

  it("renders momentum arrow", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByTestId("momentum-arrow")).toBeInTheDocument();
  });

  it("renders stat row with 4 stats", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    const statRow = screen.getByTestId("stat-row");
    expect(statRow).toBeInTheDocument();
    expect(statRow).toHaveTextContent("salience");
    expect(statRow).toHaveTextContent("valence");
    expect(statRow).toHaveTextContent("sources");
    expect(statRow).toHaveTextContent("clusters");
  });

  it("renders salience value", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByTestId("stat-row")).toHaveTextContent("2.1");
  });

  it("renders valence with sign", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByTestId("stat-row")).toHaveTextContent("-0.17");
  });

  it("renders positive valence with + prefix", () => {
    render(
      <KeywordOverviewCard
        {...baseProps}
        latest={makePerception({ valence: 0.25 })}
      />,
    );
    expect(screen.getByTestId("stat-row")).toHaveTextContent("+0.25");
  });

  it("renders source count", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByTestId("stat-row")).toHaveTextContent("12");
  });

  it("renders cluster count", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByTestId("stat-row")).toHaveTextContent("4");
  });

  it("renders mini chart", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByTestId("mini-chart")).toBeInTheDocument();
  });

  it("renders loading skeleton when history loading", () => {
    render(
      <KeywordOverviewCard {...baseProps} isHistoryLoading={true} />,
    );
    expect(screen.queryByTestId("mini-chart")).toBeNull();
  });

  it("renders waiting message when no latest data", () => {
    render(<KeywordOverviewCard {...baseProps} latest={null} />);
    expect(screen.getByTestId("waiting-message")).toHaveTextContent(
      "Waiting for first scan...",
    );
    expect(screen.queryByTestId("perception-value")).toBeNull();
    expect(screen.queryByTestId("stat-row")).toBeNull();
  });

  it("calls onExpand when expand button clicked", () => {
    const onExpand = vi.fn();
    render(<KeywordOverviewCard {...baseProps} onExpand={onExpand} />);
    fireEvent.click(screen.getByTestId("expand-btn"));
    expect(onExpand).toHaveBeenCalledOnce();
  });

  it("calls onRemove when remove button clicked", () => {
    const onRemove = vi.fn();
    render(<KeywordOverviewCard {...baseProps} onRemove={onRemove} />);
    fireEvent.click(screen.getByTestId("remove-keyword-btn"));
    expect(onRemove).toHaveBeenCalledOnce();
  });

  it("shows expand button text", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(screen.getByTestId("expand-btn")).toHaveTextContent(
      "View details",
    );
  });

  it("renders card with keyword-specific test id", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(
      screen.getByTestId(`keyword-card-${baseProps.keyword.id}`),
    ).toBeInTheDocument();
  });

  it("shows perception pressure label", () => {
    render(<KeywordOverviewCard {...baseProps} />);
    expect(
      screen.getByText("perception pressure"),
    ).toBeInTheDocument();
  });
});
