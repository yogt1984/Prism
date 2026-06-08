import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PerspectiveViewer from "@/components/story/PerspectiveViewer";
import { makePerspective, makeSource } from "../helpers/fixtures";
import type { Source } from "@/lib/types";

function makeSourceMap(sources: Source[]): Map<number, Source> {
  return new Map(sources.map((s) => [s.id, s]));
}

describe("PerspectiveViewer", () => {
  describe("empty state", () => {
    it("shows analyzing message when no perspectives", () => {
      render(
        <PerspectiveViewer
          perspectives={[]}
          sourceMap={new Map()}
        />,
      );
      expect(
        screen.getByTestId("perspectives-analyzing"),
      ).toBeInTheDocument();
    });

    it("shows descriptive text in empty state", () => {
      render(
        <PerspectiveViewer
          perspectives={[]}
          sourceMap={new Map()}
        />,
      );
      expect(
        screen.getByText(/perspectives coming soon/i),
      ).toBeInTheDocument();
    });

    it("does not show view toggle when empty", () => {
      render(
        <PerspectiveViewer
          perspectives={[]}
          sourceMap={new Map()}
        />,
      );
      expect(screen.queryByTestId("view-toggle")).not.toBeInTheDocument();
    });
  });

  describe("single perspective", () => {
    it("renders without view toggle", () => {
      const perspectives = [makePerspective({ id: 1 })];
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={new Map()}
        />,
      );
      expect(screen.queryByTestId("view-toggle")).not.toBeInTheDocument();
    });

    it('shows "Only one source covered this story"', () => {
      const perspectives = [makePerspective({ id: 1 })];
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={new Map()}
        />,
      );
      expect(
        screen.getByText("Only one source covered this story"),
      ).toBeInTheDocument();
    });

    it("renders single perspective card", () => {
      const perspectives = [makePerspective({ id: 1 })];
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={new Map()}
        />,
      );
      expect(screen.getAllByTestId("perspective-card")).toHaveLength(1);
    });

    it("uses grid-cols-1 for single perspective", () => {
      const perspectives = [makePerspective({ id: 1 })];
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={new Map()}
        />,
      );
      const grid = screen.getByTestId("perspective-grid");
      expect(grid.className).toContain("grid-cols-1");
      expect(grid.className).not.toContain("lg:grid-cols-2");
    });
  });

  describe("multiple perspectives — side-by-side (default)", () => {
    const perspectives = [
      makePerspective({ id: 1, source_id: 1 }),
      makePerspective({ id: 2, source_id: 2 }),
    ];
    const sources = [
      makeSource({ id: 1, name: "Reuters" }),
      makeSource({ id: 2, name: "AP" }),
    ];
    const sourceMap = makeSourceMap(sources);

    it("renders grid view by default", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      expect(screen.getByTestId("perspective-grid")).toBeInTheDocument();
    });

    it("renders all perspective cards", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      expect(screen.getAllByTestId("perspective-card")).toHaveLength(2);
    });

    it("shows view toggle for multiple perspectives", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      expect(screen.getByTestId("view-toggle")).toBeInTheDocument();
    });

    it("shows Grid, Stack, Tabs toggle buttons", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      expect(screen.getByText("Grid")).toBeInTheDocument();
      expect(screen.getByText("Stack")).toBeInTheDocument();
      expect(screen.getByText("Tabs")).toBeInTheDocument();
    });

    it("uses lg:grid-cols-2 for 2 perspectives", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      const grid = screen.getByTestId("perspective-grid");
      expect(grid.className).toContain("lg:grid-cols-2");
    });

    it("does not show single-source message", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      expect(
        screen.queryByText("Only one source covered this story"),
      ).not.toBeInTheDocument();
    });
  });

  describe("3+ perspectives grid", () => {
    it("uses xl:grid-cols-3 for 3 perspectives", () => {
      const perspectives = [
        makePerspective({ id: 1 }),
        makePerspective({ id: 2 }),
        makePerspective({ id: 3 }),
      ];
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={new Map()}
        />,
      );
      const grid = screen.getByTestId("perspective-grid");
      expect(grid.className).toContain("xl:grid-cols-3");
    });
  });

  describe("stacked mode", () => {
    it("switches to stacked view", () => {
      const perspectives = [
        makePerspective({ id: 1 }),
        makePerspective({ id: 2 }),
      ];
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={new Map()}
        />,
      );
      fireEvent.click(screen.getByText("Stack"));
      expect(screen.getByTestId("perspective-stack")).toBeInTheDocument();
      expect(
        screen.queryByTestId("perspective-grid"),
      ).not.toBeInTheDocument();
    });

    it("renders all cards in stacked mode", () => {
      const perspectives = [
        makePerspective({ id: 1 }),
        makePerspective({ id: 2 }),
        makePerspective({ id: 3 }),
      ];
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={new Map()}
        />,
      );
      fireEvent.click(screen.getByText("Stack"));
      expect(screen.getAllByTestId("perspective-card")).toHaveLength(3);
    });
  });

  describe("tabbed mode", () => {
    const perspectives = [
      makePerspective({ id: 1, source_id: 1 }),
      makePerspective({ id: 2, source_id: 2 }),
    ];
    const sources = [
      makeSource({ id: 1, name: "Reuters" }),
      makeSource({ id: 2, name: "AP" }),
    ];
    const sourceMap = makeSourceMap(sources);

    it("switches to tabbed view", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      fireEvent.click(screen.getByText("Tabs"));
      expect(screen.getByTestId("perspective-tabs")).toBeInTheDocument();
    });

    it("renders one card at a time in tabbed mode", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      fireEvent.click(screen.getByText("Tabs"));
      expect(screen.getAllByTestId("perspective-card")).toHaveLength(1);
    });

    it("shows tab buttons with source names", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      fireEvent.click(screen.getByText("Tabs"));
      // Tab buttons show source names
      const tabs = screen.getByTestId("perspective-tabs");
      expect(tabs).toBeInTheDocument();
    });

    it("shows first tab by default", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      fireEvent.click(screen.getByText("Tabs"));
      // First perspective's summary should be visible
      expect(
        screen.getByText(perspectives[0].summary),
      ).toBeInTheDocument();
    });

    it("switches tab on click", () => {
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={sourceMap}
        />,
      );
      fireEvent.click(screen.getByText("Tabs"));

      // Click the second tab (AP)
      const tabButtons = screen
        .getByTestId("perspective-tabs")
        .querySelectorAll("button");
      fireEvent.click(tabButtons[1]);

      expect(
        screen.getByText(perspectives[1].summary),
      ).toBeInTheDocument();
    });

    it("falls back to Source #id when source not in map", () => {
      const p = [
        makePerspective({ id: 1, source_id: 999 }),
        makePerspective({ id: 2, source_id: 888 }),
      ];
      render(
        <PerspectiveViewer perspectives={p} sourceMap={new Map()} />,
      );
      fireEvent.click(screen.getByText("Tabs"));
      // Tab button + card both show the fallback name
      expect(screen.getAllByText("Source #999").length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("mode switching", () => {
    it("can switch between all three modes", () => {
      const perspectives = [
        makePerspective({ id: 1 }),
        makePerspective({ id: 2 }),
      ];
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={new Map()}
        />,
      );

      // Default: grid
      expect(screen.getByTestId("perspective-grid")).toBeInTheDocument();

      // Switch to stack
      fireEvent.click(screen.getByText("Stack"));
      expect(screen.getByTestId("perspective-stack")).toBeInTheDocument();
      expect(
        screen.queryByTestId("perspective-grid"),
      ).not.toBeInTheDocument();

      // Switch to tabs
      fireEvent.click(screen.getByText("Tabs"));
      expect(screen.getByTestId("perspective-tabs")).toBeInTheDocument();
      expect(
        screen.queryByTestId("perspective-stack"),
      ).not.toBeInTheDocument();

      // Switch back to grid
      fireEvent.click(screen.getByText("Grid"));
      expect(screen.getByTestId("perspective-grid")).toBeInTheDocument();
      expect(
        screen.queryByTestId("perspective-tabs"),
      ).not.toBeInTheDocument();
    });

    it("highlights active mode button", () => {
      const perspectives = [
        makePerspective({ id: 1 }),
        makePerspective({ id: 2 }),
      ];
      render(
        <PerspectiveViewer
          perspectives={perspectives}
          sourceMap={new Map()}
        />,
      );

      // Grid should be active by default
      const gridBtn = screen.getByText("Grid");
      expect(gridBtn.className).toContain("bg-violet-100");

      // Switch to Stack
      fireEvent.click(screen.getByText("Stack"));
      const stackBtn = screen.getByText("Stack");
      expect(stackBtn.className).toContain("bg-violet-100");
      expect(screen.getByText("Grid").className).not.toContain(
        "bg-violet-100",
      );
    });
  });
});
