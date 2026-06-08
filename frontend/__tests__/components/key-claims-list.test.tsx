import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import KeyClaimsList from "@/components/story/KeyClaimsList";

describe("KeyClaimsList", () => {
  it("renders claims from valid JSON", () => {
    const json = JSON.stringify(["Claim one", "Claim two", "Claim three"]);
    render(<KeyClaimsList claimsJson={json} />);
    expect(screen.getByTestId("key-claims")).toBeInTheDocument();
    expect(screen.getByText("Claim one")).toBeInTheDocument();
    expect(screen.getByText("Claim two")).toBeInTheDocument();
    expect(screen.getByText("Claim three")).toBeInTheDocument();
  });

  it("renders correct number of list items", () => {
    const json = JSON.stringify(["A", "B", "C", "D"]);
    render(<KeyClaimsList claimsJson={json} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(4);
  });

  it("returns null for invalid JSON", () => {
    const { container } = render(
      <KeyClaimsList claimsJson="not valid json" />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("returns null for empty string", () => {
    const { container } = render(<KeyClaimsList claimsJson="" />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null for empty array", () => {
    const { container } = render(<KeyClaimsList claimsJson="[]" />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null for non-array JSON (object)", () => {
    const { container } = render(
      <KeyClaimsList claimsJson='{"key": "value"}' />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("returns null for non-array JSON (string)", () => {
    const { container } = render(
      <KeyClaimsList claimsJson='"just a string"' />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("returns null for non-array JSON (number)", () => {
    const { container } = render(<KeyClaimsList claimsJson="42" />);
    expect(container.innerHTML).toBe("");
  });

  it("renders single claim", () => {
    const json = JSON.stringify(["Only one claim"]);
    render(<KeyClaimsList claimsJson={json} />);
    expect(screen.getByText("Only one claim")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });

  it("renders claims with special characters", () => {
    const json = JSON.stringify([
      'The rate is 5.25% - "steady"',
      "GDP grew <3%",
    ]);
    render(<KeyClaimsList claimsJson={json} />);
    expect(
      screen.getByText('The rate is 5.25% - "steady"'),
    ).toBeInTheDocument();
    expect(screen.getByText("GDP grew <3%")).toBeInTheDocument();
  });

  it("uses disc list style", () => {
    const json = JSON.stringify(["A"]);
    render(<KeyClaimsList claimsJson={json} />);
    expect(screen.getByTestId("key-claims").className).toContain("list-disc");
  });
});
