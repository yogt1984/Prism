import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusBadge, { STATUS_STYLES } from "@/components/sources/StatusBadge";
import type { SourceStatus } from "@/lib/types";

const ALL_STATUSES: SourceStatus[] = [
  "seed",
  "candidate",
  "probation",
  "trusted",
  "rejected",
];

describe("StatusBadge", () => {
  it.each(ALL_STATUSES)("renders correct text for %s", (status) => {
    render(<StatusBadge status={status} />);
    const badge = screen.getByTestId("status-badge");
    expect(badge).toHaveTextContent(STATUS_STYLES[status].text);
  });

  it.each(ALL_STATUSES)("applies color classes for %s", (status) => {
    render(<StatusBadge status={status} />);
    const badge = screen.getByTestId("status-badge");
    const colorClasses = STATUS_STYLES[status].color.split(" ");
    for (const cls of colorClasses) {
      expect(badge.className).toContain(cls);
    }
  });

  it("has status-badge test id", () => {
    render(<StatusBadge status="trusted" />);
    expect(screen.getByTestId("status-badge")).toBeInTheDocument();
  });
});

describe("STATUS_STYLES", () => {
  it("has entries for all 5 statuses", () => {
    expect(Object.keys(STATUS_STYLES)).toHaveLength(5);
    for (const status of ALL_STATUSES) {
      expect(STATUS_STYLES[status]).toBeDefined();
    }
  });
});
