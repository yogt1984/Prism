import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import BriefingNav from "@/components/briefing/BriefingNav";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("BriefingNav", () => {
  it("renders nothing when both prevId and nextId are null", () => {
    const { container } = render(
      <BriefingNav prevId={null} nextId={null} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders previous link when prevId provided", () => {
    render(<BriefingNav prevId={41} nextId={null} />);
    const link = screen.getByTestId("nav-prev");
    expect(link).toHaveAttribute("href", "/briefings/41");
    expect(link).toHaveTextContent("Previous briefing");
  });

  it("renders next link when nextId provided", () => {
    render(<BriefingNav prevId={null} nextId={43} />);
    const link = screen.getByTestId("nav-next");
    expect(link).toHaveAttribute("href", "/briefings/43");
    expect(link).toHaveTextContent("Next briefing");
  });

  it("renders both links when both provided", () => {
    render(<BriefingNav prevId={41} nextId={43} />);
    expect(screen.getByTestId("nav-prev")).toBeInTheDocument();
    expect(screen.getByTestId("nav-next")).toBeInTheDocument();
  });

  it("hides previous link when prevId is null", () => {
    render(<BriefingNav prevId={null} nextId={43} />);
    expect(screen.queryByTestId("nav-prev")).not.toBeInTheDocument();
  });

  it("hides next link when nextId is null", () => {
    render(<BriefingNav prevId={41} nextId={null} />);
    expect(screen.queryByTestId("nav-next")).not.toBeInTheDocument();
  });

  it("uses correct href format", () => {
    render(<BriefingNav prevId={100} nextId={200} />);
    expect(screen.getByTestId("nav-prev")).toHaveAttribute(
      "href",
      "/briefings/100",
    );
    expect(screen.getByTestId("nav-next")).toHaveAttribute(
      "href",
      "/briefings/200",
    );
  });
});
