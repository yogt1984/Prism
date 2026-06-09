import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import LifecycleInfo from "@/components/sources/LifecycleInfo";
import { makeSource } from "../helpers/fixtures";

describe("LifecycleInfo", () => {
  it("renders sighting count for candidate", () => {
    const source = makeSource({ status: "candidate", sighting_count: 12 });
    render(<LifecycleInfo source={source} />);
    expect(screen.getByTestId("lifecycle-info")).toHaveTextContent(
      "12 sightings",
    );
  });

  it("renders singular for 1 sighting", () => {
    const source = makeSource({ status: "candidate", sighting_count: 1 });
    render(<LifecycleInfo source={source} />);
    expect(screen.getByTestId("lifecycle-info")).toHaveTextContent(
      "1 sighting",
    );
  });

  it("renders validation ratio for probation", () => {
    const source = makeSource({
      status: "probation",
      articles_validated: 8,
      articles_failed: 2,
    });
    render(<LifecycleInfo source={source} />);
    expect(screen.getByTestId("lifecycle-info")).toHaveTextContent(
      "8/10 validated",
    );
  });

  it("renders 0/0 for probation with no articles", () => {
    const source = makeSource({
      status: "probation",
      articles_validated: 0,
      articles_failed: 0,
    });
    render(<LifecycleInfo source={source} />);
    expect(screen.getByTestId("lifecycle-info")).toHaveTextContent(
      "0/0 validated",
    );
  });

  it("returns null for trusted", () => {
    const source = makeSource({ status: "trusted" });
    const { container } = render(<LifecycleInfo source={source} />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null for seed", () => {
    const source = makeSource({ status: "seed" });
    const { container } = render(<LifecycleInfo source={source} />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null for rejected", () => {
    const source = makeSource({ status: "rejected" });
    const { container } = render(<LifecycleInfo source={source} />);
    expect(container.innerHTML).toBe("");
  });
});
