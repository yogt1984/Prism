import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ArticleSourcesList from "@/components/story/ArticleSourcesList";
import { makeArticle, makeSource } from "../helpers/fixtures";
import type { Source } from "@/lib/types";

vi.mock("@/components/dashboard/TimeAgo", () => ({
  default: ({ date }: { date: string }) => (
    <span data-testid="time-ago">{date}</span>
  ),
}));

function makeSourceMap(sources: Source[]): Map<number, Source> {
  return new Map(sources.map((s) => [s.id, s]));
}

describe("ArticleSourcesList", () => {
  it("renders nothing when articles array is empty", () => {
    const { container } = render(
      <ArticleSourcesList articles={[]} sourceMap={new Map()} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders article list when articles present", () => {
    const articles = [makeArticle({ id: 1, source_id: 1 })];
    render(
      <ArticleSourcesList articles={articles} sourceMap={new Map()} />,
    );
    expect(screen.getByTestId("article-list")).toBeInTheDocument();
  });

  it('renders "Original Sources" heading', () => {
    const articles = [makeArticle()];
    render(
      <ArticleSourcesList articles={articles} sourceMap={new Map()} />,
    );
    expect(screen.getByText("Original Sources")).toBeInTheDocument();
  });

  it("renders correct number of article rows", () => {
    const articles = [
      makeArticle({ id: 1 }),
      makeArticle({ id: 2 }),
      makeArticle({ id: 3 }),
    ];
    render(
      <ArticleSourcesList articles={articles} sourceMap={new Map()} />,
    );
    expect(screen.getAllByTestId("article-row")).toHaveLength(3);
  });

  it("displays source name when source found in map", () => {
    const articles = [makeArticle({ id: 1, source_id: 1 })];
    const sourceMap = makeSourceMap([
      makeSource({ id: 1, name: "Reuters" }),
    ]);
    render(
      <ArticleSourcesList articles={articles} sourceMap={sourceMap} />,
    );
    expect(screen.getByText("Reuters")).toBeInTheDocument();
  });

  it("falls back to #source_id when source not in map", () => {
    const articles = [makeArticle({ id: 1, source_id: 42 })];
    render(
      <ArticleSourcesList articles={articles} sourceMap={new Map()} />,
    );
    expect(screen.getByText("#42")).toBeInTheDocument();
  });

  it("renders article title as external link", () => {
    const articles = [
      makeArticle({
        id: 1,
        title: "Big News Article",
        url: "https://example.com/article",
      }),
    ];
    render(
      <ArticleSourcesList articles={articles} sourceMap={new Map()} />,
    );
    const link = screen.getByText("Big News Article");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "https://example.com/article");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders time ago for articles with published_at", () => {
    const articles = [
      makeArticle({
        id: 1,
        published_at: "2026-01-15T12:00:00Z",
      }),
    ];
    render(
      <ArticleSourcesList articles={articles} sourceMap={new Map()} />,
    );
    expect(screen.getByTestId("time-ago")).toBeInTheDocument();
  });

  it("does not render time ago when published_at is null", () => {
    const articles = [
      makeArticle({ id: 1, published_at: null }),
    ];
    render(
      <ArticleSourcesList articles={articles} sourceMap={new Map()} />,
    );
    expect(screen.queryByTestId("time-ago")).not.toBeInTheDocument();
  });

  it("renders multiple articles with different sources", () => {
    const articles = [
      makeArticle({ id: 1, source_id: 1, title: "Reuters Article" }),
      makeArticle({ id: 2, source_id: 2, title: "AP Article" }),
    ];
    const sourceMap = makeSourceMap([
      makeSource({ id: 1, name: "Reuters" }),
      makeSource({ id: 2, name: "AP News" }),
    ]);
    render(
      <ArticleSourcesList articles={articles} sourceMap={sourceMap} />,
    );
    expect(screen.getByText("Reuters")).toBeInTheDocument();
    expect(screen.getByText("AP News")).toBeInTheDocument();
    expect(screen.getByText("Reuters Article")).toBeInTheDocument();
    expect(screen.getByText("AP Article")).toBeInTheDocument();
  });
});
