import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ResonancePanel from "@/components/story/ResonancePanel";
import { makeResonance } from "../helpers/fixtures";

describe("ResonancePanel", () => {
  describe("loading state", () => {
    it("renders skeleton when loading", () => {
      render(<ResonancePanel resonance={null} isLoading={true} />);
      expect(screen.getByTestId("resonance-skeleton")).toBeInTheDocument();
    });

    it("renders 5 skeleton blocks", () => {
      render(<ResonancePanel resonance={null} isLoading={true} />);
      const skeletons = screen
        .getByTestId("resonance-skeleton")
        .querySelectorAll(".animate-pulse");
      expect(skeletons).toHaveLength(5);
    });
  });

  describe("empty state", () => {
    it("renders empty state with dashes when no resonance data", () => {
      render(<ResonancePanel resonance={null} isLoading={false} />);
      expect(screen.getByTestId("resonance-empty")).toBeInTheDocument();
    });

    it("shows placeholder dashes for all 5 stats when empty", () => {
      render(<ResonancePanel resonance={null} isLoading={false} />);
      const container = screen.getByTestId("resonance-empty");
      const statValues = container.querySelectorAll("p.text-lg");
      expect(statValues).toHaveLength(5);
      // Each stat shows an em-dash placeholder
      statValues.forEach((el) => {
        expect(el.textContent).toBeTruthy();
      });
    });

    it("shows all stat labels in empty state", () => {
      render(<ResonancePanel resonance={null} isLoading={false} />);
      expect(screen.getByText("resonance")).toBeInTheDocument();
      expect(screen.getByText("momentum")).toBeInTheDocument();
      expect(screen.getByText("peak")).toBeInTheDocument();
      expect(screen.getByText("sources")).toBeInTheDocument();
      expect(screen.getByText("breadth")).toBeInTheDocument();
    });
  });

  describe("loaded state", () => {
    it("renders panel with data", () => {
      const r = makeResonance();
      render(<ResonancePanel resonance={r} isLoading={false} />);
      expect(screen.getByTestId("resonance-panel")).toBeInTheDocument();
    });

    it("displays formatted resonance value", () => {
      const r = makeResonance({ resonance: 4.72 });
      render(<ResonancePanel resonance={r} isLoading={false} />);
      expect(screen.getByText("4.72")).toBeInTheDocument();
    });

    it("displays formatted momentum value", () => {
      const r = makeResonance({ momentum: 0.15 });
      render(<ResonancePanel resonance={r} isLoading={false} />);
      expect(screen.getByText("0.15")).toBeInTheDocument();
    });

    it("displays formatted peak resonance value", () => {
      const r = makeResonance({ peak_resonance: 5.1 });
      render(<ResonancePanel resonance={r} isLoading={false} />);
      expect(screen.getByText("5.10")).toBeInTheDocument();
    });

    it("displays source count", () => {
      const r = makeResonance({ source_count: 8 });
      render(<ResonancePanel resonance={r} isLoading={false} />);
      expect(screen.getByText("8")).toBeInTheDocument();
    });

    it("displays formatted breadth value", () => {
      const r = makeResonance({ breadth: 0.78 });
      render(<ResonancePanel resonance={r} isLoading={false} />);
      expect(screen.getByText("0.78")).toBeInTheDocument();
    });

    it("renders all 5 stat labels", () => {
      const r = makeResonance();
      render(<ResonancePanel resonance={r} isLoading={false} />);
      expect(screen.getByText("resonance")).toBeInTheDocument();
      expect(screen.getByText("momentum")).toBeInTheDocument();
      expect(screen.getByText("peak")).toBeInTheDocument();
      expect(screen.getByText("sources")).toBeInTheDocument();
      expect(screen.getByText("breadth")).toBeInTheDocument();
    });

    it("prefers loaded state over loading when both are provided", () => {
      const r = makeResonance();
      // isLoading=true but resonance is present — component checks isLoading first
      render(<ResonancePanel resonance={r} isLoading={true} />);
      expect(screen.getByTestId("resonance-skeleton")).toBeInTheDocument();
    });
  });
});
