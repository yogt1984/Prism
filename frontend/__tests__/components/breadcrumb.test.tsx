import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Breadcrumb from "@/components/story/Breadcrumb";

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

describe("Breadcrumb", () => {
  it("renders all items", () => {
    render(
      <Breadcrumb
        items={[
          { label: "Home", href: "/" },
          { label: "Stories", href: "/stories" },
          { label: "Detail" },
        ]}
      />,
    );
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Stories")).toBeInTheDocument();
    expect(screen.getByText("Detail")).toBeInTheDocument();
  });

  it("renders links for items with href", () => {
    render(
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Current" },
        ]}
      />,
    );
    const link = screen.getByText("Dashboard");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/dashboard");
  });

  it("renders plain text for items without href", () => {
    render(
      <Breadcrumb items={[{ label: "Home", href: "/" }, { label: "Current" }]} />,
    );
    const current = screen.getByText("Current");
    expect(current.tagName).toBe("SPAN");
  });

  it("renders separators between items", () => {
    const { container } = render(
      <Breadcrumb
        items={[
          { label: "A", href: "/a" },
          { label: "B", href: "/b" },
          { label: "C" },
        ]}
      />,
    );
    const separators = container.querySelectorAll("[aria-hidden]");
    expect(separators).toHaveLength(2);
    separators.forEach((sep) => expect(sep.textContent).toBe("/"));
  });

  it("does not render separator before first item", () => {
    const { container } = render(
      <Breadcrumb items={[{ label: "Only" }]} />,
    );
    expect(container.querySelectorAll("[aria-hidden]")).toHaveLength(0);
  });

  it("has breadcrumb aria label for navigation", () => {
    render(<Breadcrumb items={[{ label: "Home" }]} />);
    expect(screen.getByRole("navigation")).toHaveAttribute(
      "aria-label",
      "Breadcrumb",
    );
  });

  it("truncates long last item", () => {
    render(
      <Breadcrumb
        items={[
          { label: "Home", href: "/" },
          { label: "A Very Long Story Headline That Should Be Truncated" },
        ]}
      />,
    );
    const lastItem = screen.getByText(
      "A Very Long Story Headline That Should Be Truncated",
    );
    expect(lastItem.className).toContain("truncate");
  });

  it("renders single item without separator", () => {
    render(<Breadcrumb items={[{ label: "Home", href: "/" }]} />);
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.queryByText("/")).not.toBeInTheDocument();
  });
});
