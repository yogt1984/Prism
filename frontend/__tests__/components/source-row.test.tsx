import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  SourceTableRow,
  SourceCard,
  getFaviconUrl,
  getDomain,
  getCategories,
} from "@/components/sources/SourceRow";
import { makeSource } from "../helpers/fixtures";

describe("getFaviconUrl", () => {
  it("extracts hostname for favicon URL", () => {
    expect(getFaviconUrl("https://www.reuters.com")).toBe(
      "https://www.google.com/s2/favicons?domain=www.reuters.com&sz=32",
    );
  });

  it("returns fallback for invalid URL", () => {
    expect(getFaviconUrl("not-a-url")).toBe("/icons/globe.svg");
  });
});

describe("getDomain", () => {
  it("strips www prefix", () => {
    expect(getDomain("https://www.reuters.com")).toBe("reuters.com");
  });

  it("preserves non-www subdomains", () => {
    expect(getDomain("https://news.bbc.com")).toBe("news.bbc.com");
  });

  it("returns raw string for invalid URL", () => {
    expect(getDomain("invalid")).toBe("invalid");
  });
});

describe("getCategories", () => {
  it("splits comma-separated categories", () => {
    expect(getCategories("finance,politics,world")).toEqual([
      "finance",
      "politics",
      "world",
    ]);
  });

  it("trims whitespace", () => {
    expect(getCategories("finance , politics")).toEqual(["finance", "politics"]);
  });

  it("filters empty strings", () => {
    expect(getCategories("finance,,politics")).toEqual(["finance", "politics"]);
  });

  it("handles single category", () => {
    expect(getCategories("finance")).toEqual(["finance"]);
  });
});

describe("SourceTableRow", () => {
  const source = makeSource({
    name: "Reuters",
    url: "https://www.reuters.com",
    trust_score: 0.92,
    bias_label: "center",
    categories: "finance,world",
  });

  it("renders source name", () => {
    const { container } = render(
      <table>
        <tbody>
          <SourceTableRow source={source} />
        </tbody>
      </table>,
    );
    expect(container).toHaveTextContent("Reuters");
  });

  it("renders domain text", () => {
    const { container } = render(
      <table>
        <tbody>
          <SourceTableRow source={source} />
        </tbody>
      </table>,
    );
    expect(container).toHaveTextContent("reuters.com");
  });

  it("renders trust bar", () => {
    render(
      <table>
        <tbody>
          <SourceTableRow source={source} />
        </tbody>
      </table>,
    );
    expect(screen.getByTestId("trust-bar")).toBeInTheDocument();
    expect(screen.getByTestId("trust-value")).toHaveTextContent("0.92");
  });

  it("renders bias label badge", () => {
    render(
      <table>
        <tbody>
          <SourceTableRow source={source} />
        </tbody>
      </table>,
    );
    expect(screen.getByTestId("bias-label")).toHaveTextContent("Center");
  });

  it("renders View stories link with correct href", () => {
    render(
      <table>
        <tbody>
          <SourceTableRow source={source} />
        </tbody>
      </table>,
    );
    const link = screen.getByTestId("stories-link");
    expect(link).toHaveAttribute("href", `/stories?source=${source.id}`);
    expect(link).toHaveTextContent("View");
  });

  it("renders favicon image", () => {
    render(
      <table>
        <tbody>
          <SourceTableRow source={source} />
        </tbody>
      </table>,
    );
    expect(screen.getByTestId("favicon")).toBeInTheDocument();
  });

  it("has source-row test id", () => {
    render(
      <table>
        <tbody>
          <SourceTableRow source={source} />
        </tbody>
      </table>,
    );
    expect(screen.getByTestId("source-row")).toBeInTheDocument();
  });
});

describe("SourceCard", () => {
  const source = makeSource({
    name: "BBC",
    url: "https://www.bbc.com",
    trust_score: 0.85,
    bias_label: "center_left",
    categories: "world,culture,technology",
  });

  it("renders source name", () => {
    render(<SourceCard source={source} />);
    expect(screen.getByText("BBC")).toBeInTheDocument();
  });

  it("renders domain", () => {
    render(<SourceCard source={source} />);
    expect(screen.getByText("bbc.com")).toBeInTheDocument();
  });

  it("renders trust bar with value", () => {
    render(<SourceCard source={source} />);
    expect(screen.getByTestId("trust-value")).toHaveTextContent("0.85");
  });

  it("renders bias label", () => {
    render(<SourceCard source={source} />);
    expect(screen.getByTestId("bias-label")).toHaveTextContent("Center-Left");
  });

  it("renders category pills", () => {
    render(<SourceCard source={source} />);
    expect(screen.getByText("world")).toBeInTheDocument();
    expect(screen.getByText("culture")).toBeInTheDocument();
    expect(screen.getByText("technology")).toBeInTheDocument();
  });

  it("renders View stories link", () => {
    render(<SourceCard source={source} />);
    const link = screen.getByTestId("stories-link");
    expect(link).toHaveAttribute("href", `/stories?source=${source.id}`);
  });

  it("has source-card test id", () => {
    render(<SourceCard source={source} />);
    expect(screen.getByTestId("source-card")).toBeInTheDocument();
  });

  it("renders favicon", () => {
    render(<SourceCard source={source} />);
    expect(screen.getByTestId("favicon")).toBeInTheDocument();
  });
});
