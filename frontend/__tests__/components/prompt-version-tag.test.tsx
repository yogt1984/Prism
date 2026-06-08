import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PromptVersionTag from "@/components/briefing/PromptVersionTag";

describe("PromptVersionTag", () => {
  it("renders version string", () => {
    render(<PromptVersionTag version="v2" />);
    expect(screen.getByTestId("prompt-version-tag")).toHaveTextContent("v2");
  });

  it("renders different version", () => {
    render(<PromptVersionTag version="v3.1" />);
    expect(screen.getByTestId("prompt-version-tag")).toHaveTextContent(
      "v3.1",
    );
  });

  it("has gray styling", () => {
    render(<PromptVersionTag version="v2" />);
    const el = screen.getByTestId("prompt-version-tag");
    expect(el.className).toContain("bg-gray-100");
  });
});
