import { describe, it, expect, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import HTMLRenderer, {
  ALLOWED_TAGS,
  ALLOWED_ATTRS,
} from "@/components/briefing/HTMLRenderer";

describe("HTMLRenderer", () => {
  afterEach(() => {
    // Clean up DOMPurify hooks between tests
  });

  it("renders safe HTML content", () => {
    render(<HTMLRenderer html="<h2>Morning Briefing</h2><p>Hello world</p>" />);
    const el = screen.getByTestId("html-renderer");
    expect(el.querySelector("h2")?.textContent).toBe("Morning Briefing");
    expect(el.querySelector("p")?.textContent).toBe("Hello world");
  });

  it("strips script tags", () => {
    render(
      <HTMLRenderer html='<p>Safe</p><script>alert("xss")</script>' />,
    );
    const el = screen.getByTestId("html-renderer");
    expect(el.innerHTML).not.toContain("<script");
    expect(el.innerHTML).not.toContain("alert");
    expect(el.querySelector("p")?.textContent).toBe("Safe");
  });

  it("strips onclick handlers", () => {
    render(
      <HTMLRenderer html='<p onclick="alert(1)">Click me</p>' />,
    );
    const el = screen.getByTestId("html-renderer");
    const p = el.querySelector("p");
    expect(p?.getAttribute("onclick")).toBeNull();
  });

  it("strips iframe tags", () => {
    render(
      <HTMLRenderer html='<iframe src="https://evil.com"></iframe><p>Safe</p>' />,
    );
    const el = screen.getByTestId("html-renderer");
    expect(el.querySelector("iframe")).toBeNull();
  });

  it("preserves allowed tags", () => {
    render(
      <HTMLRenderer html="<h1>Title</h1><h2>Sub</h2><h3>Section</h3><p>Text</p><em>italic</em><strong>bold</strong>" />,
    );
    const el = screen.getByTestId("html-renderer");
    expect(el.querySelector("h1")).toBeInTheDocument();
    expect(el.querySelector("h2")).toBeInTheDocument();
    expect(el.querySelector("h3")).toBeInTheDocument();
    expect(el.querySelector("p")).toBeInTheDocument();
    expect(el.querySelector("em")).toBeInTheDocument();
    expect(el.querySelector("strong")).toBeInTheDocument();
  });

  it("preserves lists", () => {
    render(
      <HTMLRenderer html="<ul><li>Item 1</li><li>Item 2</li></ul>" />,
    );
    const el = screen.getByTestId("html-renderer");
    expect(el.querySelectorAll("li")).toHaveLength(2);
  });

  it("preserves ordered lists", () => {
    render(
      <HTMLRenderer html="<ol><li>First</li><li>Second</li></ol>" />,
    );
    const el = screen.getByTestId("html-renderer");
    expect(el.querySelector("ol")).toBeInTheDocument();
  });

  it("preserves links with href", () => {
    render(
      <HTMLRenderer html='<a href="https://reuters.com">Reuters</a>' />,
    );
    const el = screen.getByTestId("html-renderer");
    const link = el.querySelector("a");
    expect(link).toBeInTheDocument();
    expect(link?.getAttribute("href")).toBe("https://reuters.com");
  });

  it("adds target=_blank to links", () => {
    render(
      <HTMLRenderer html='<a href="https://reuters.com">Reuters</a>' />,
    );
    const el = screen.getByTestId("html-renderer");
    const link = el.querySelector("a");
    expect(link?.getAttribute("target")).toBe("_blank");
    expect(link?.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("strips img tags (not in allowed list)", () => {
    render(
      <HTMLRenderer html='<img src="https://evil.com/track.png" /><p>Text</p>' />,
    );
    const el = screen.getByTestId("html-renderer");
    expect(el.querySelector("img")).toBeNull();
  });

  it("strips style attributes", () => {
    render(
      <HTMLRenderer html='<p style="color:red">Styled</p>' />,
    );
    const el = screen.getByTestId("html-renderer");
    const p = el.querySelector("p");
    expect(p?.getAttribute("style")).toBeNull();
  });

  it("renders empty string without error", () => {
    render(<HTMLRenderer html="" />);
    const el = screen.getByTestId("html-renderer");
    expect(el.innerHTML).toBe("");
  });

  it("applies prose class for typography styling", () => {
    render(<HTMLRenderer html="<p>Text</p>" />);
    const el = screen.getByTestId("html-renderer");
    expect(el.className).toContain("prose");
  });

  it("uses article element", () => {
    render(<HTMLRenderer html="<p>Text</p>" />);
    const el = screen.getByTestId("html-renderer");
    expect(el.tagName).toBe("ARTICLE");
  });

  it("strips form elements", () => {
    render(
      <HTMLRenderer html='<form action="/hack"><input type="text" /><button>Submit</button></form><p>Safe</p>' />,
    );
    const el = screen.getByTestId("html-renderer");
    expect(el.querySelector("form")).toBeNull();
    expect(el.querySelector("input")).toBeNull();
  });

  describe("ALLOWED_TAGS constant", () => {
    it("includes all safe content tags", () => {
      expect(ALLOWED_TAGS).toContain("h1");
      expect(ALLOWED_TAGS).toContain("h2");
      expect(ALLOWED_TAGS).toContain("p");
      expect(ALLOWED_TAGS).toContain("a");
      expect(ALLOWED_TAGS).toContain("em");
      expect(ALLOWED_TAGS).toContain("strong");
      expect(ALLOWED_TAGS).toContain("ul");
      expect(ALLOWED_TAGS).toContain("ol");
      expect(ALLOWED_TAGS).toContain("li");
    });

    it("does not include dangerous tags", () => {
      expect(ALLOWED_TAGS).not.toContain("script");
      expect(ALLOWED_TAGS).not.toContain("iframe");
      expect(ALLOWED_TAGS).not.toContain("img");
      expect(ALLOWED_TAGS).not.toContain("form");
    });
  });

  describe("ALLOWED_ATTRS constant", () => {
    it("includes href, target, rel", () => {
      expect(ALLOWED_ATTRS).toContain("href");
      expect(ALLOWED_ATTRS).toContain("target");
      expect(ALLOWED_ATTRS).toContain("rel");
    });

    it("does not include style or onclick", () => {
      expect(ALLOWED_ATTRS).not.toContain("style");
      expect(ALLOWED_ATTRS).not.toContain("onclick");
    });
  });
});
