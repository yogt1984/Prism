import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import KeywordItem from "@/components/dashboard/KeywordItem";
import { makePerceptionHistory } from "../helpers/fixtures";

describe("KeywordItem", () => {
  it("renders keyword name", () => {
    render(
      <KeywordItem keyword="tariffs" history={[]} isLoading={false} />,
    );
    expect(screen.getByText("tariffs")).toBeInTheDocument();
  });

  it("shows loading skeleton when isLoading", () => {
    render(
      <KeywordItem keyword="tariffs" history={[]} isLoading={true} />,
    );
    expect(screen.getByTestId("keyword-skeleton")).toBeInTheDocument();
  });

  it("does not show skeleton when loaded", () => {
    render(
      <KeywordItem keyword="tariffs" history={[]} isLoading={false} />,
    );
    expect(screen.queryByTestId("keyword-skeleton")).toBeNull();
  });

  it("renders sparkline when history is provided", () => {
    const history = makePerceptionHistory(10);
    render(
      <KeywordItem keyword="tariffs" history={history} isLoading={false} />,
    );
    expect(
      screen.getByRole("img", { name: "Perception sparkline" }),
    ).toBeInTheDocument();
  });

  it("does not render sparkline with empty history", () => {
    render(
      <KeywordItem keyword="tariffs" history={[]} isLoading={false} />,
    );
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("renders momentum arrow from latest data point", () => {
    const history = makePerceptionHistory(5);
    // The last point has momentum 0.15 (positive)
    render(
      <KeywordItem keyword="tariffs" history={history} isLoading={false} />,
    );
    expect(screen.getByLabelText("rising")).toBeInTheDocument();
  });

  it("has keyword-item testid", () => {
    render(
      <KeywordItem keyword="tariffs" history={[]} isLoading={false} />,
    );
    expect(screen.getByTestId("keyword-item")).toBeInTheDocument();
  });
});
