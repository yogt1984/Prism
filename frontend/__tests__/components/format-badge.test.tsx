import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FormatBadge, {
  FORMAT_LABELS,
} from "@/components/briefing/FormatBadge";
import type { BriefingFormat } from "@/lib/types";

describe("FormatBadge", () => {
  it('renders "Email" for email format', () => {
    render(<FormatBadge format="email" />);
    expect(screen.getByTestId("format-badge")).toHaveTextContent("Email");
  });

  it('renders "JSON Feed" for json_feed format', () => {
    render(<FormatBadge format="json_feed" />);
    expect(screen.getByTestId("format-badge")).toHaveTextContent("JSON Feed");
  });

  it('renders "Audio" for audio_script format', () => {
    render(<FormatBadge format="audio_script" />);
    expect(screen.getByTestId("format-badge")).toHaveTextContent("Audio");
  });

  it("has blue styling", () => {
    render(<FormatBadge format="email" />);
    const el = screen.getByTestId("format-badge");
    expect(el.className).toContain("bg-blue-100");
    expect(el.className).toContain("text-blue-700");
  });

  it("FORMAT_LABELS covers all formats", () => {
    const formats: BriefingFormat[] = ["email", "json_feed", "audio_script"];
    formats.forEach((f) => {
      expect(FORMAT_LABELS[f]).toBeTruthy();
    });
  });
});
