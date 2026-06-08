import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FormatSelector, {
  FORMAT_OPTIONS,
} from "@/components/settings/FormatSelector";

describe("FormatSelector", () => {
  it("renders all 3 format options", () => {
    render(
      <FormatSelector value="email" onChange={vi.fn()} isPro={true} />,
    );
    expect(screen.getByTestId("format-option-email")).toBeInTheDocument();
    expect(
      screen.getByTestId("format-option-json_feed"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("format-option-audio_script"),
    ).toBeInTheDocument();
  });

  it("checks the selected format", () => {
    render(
      <FormatSelector value="email" onChange={vi.fn()} isPro={true} />,
    );
    const radio = screen
      .getByTestId("format-option-email")
      .querySelector("input");
    expect(radio).toBeChecked();
  });

  it("calls onChange when a format is selected", () => {
    const onChange = vi.fn();
    render(
      <FormatSelector value="email" onChange={onChange} isPro={true} />,
    );
    const radio = screen
      .getByTestId("format-option-json_feed")
      .querySelector("input")!;
    fireEvent.click(radio);
    expect(onChange).toHaveBeenCalledWith("json_feed");
  });

  it("disables pro-only formats for free users", () => {
    render(
      <FormatSelector value="email" onChange={vi.fn()} isPro={false} />,
    );
    const jsonRadio = screen
      .getByTestId("format-option-json_feed")
      .querySelector("input");
    const audioRadio = screen
      .getByTestId("format-option-audio_script")
      .querySelector("input");
    expect(jsonRadio).toBeDisabled();
    expect(audioRadio).toBeDisabled();
  });

  it("enables all formats for pro users", () => {
    render(
      <FormatSelector value="email" onChange={vi.fn()} isPro={true} />,
    );
    const jsonRadio = screen
      .getByTestId("format-option-json_feed")
      .querySelector("input");
    const audioRadio = screen
      .getByTestId("format-option-audio_script")
      .querySelector("input");
    expect(jsonRadio).not.toBeDisabled();
    expect(audioRadio).not.toBeDisabled();
  });

  it("email is always enabled", () => {
    render(
      <FormatSelector value="email" onChange={vi.fn()} isPro={false} />,
    );
    const radio = screen
      .getByTestId("format-option-email")
      .querySelector("input");
    expect(radio).not.toBeDisabled();
  });

  it('shows "Pro only" label on locked formats', () => {
    render(
      <FormatSelector value="email" onChange={vi.fn()} isPro={false} />,
    );
    const locks = screen.getAllByTestId("pro-lock");
    expect(locks).toHaveLength(2);
  });

  it('does not show "Pro only" labels for pro users', () => {
    render(
      <FormatSelector value="email" onChange={vi.fn()} isPro={true} />,
    );
    expect(screen.queryByTestId("pro-lock")).not.toBeInTheDocument();
  });

  it("marks pro-only radio inputs as disabled for free users", () => {
    render(
      <FormatSelector value="email" onChange={vi.fn()} isPro={false} />,
    );
    const radio = screen
      .getByTestId("format-option-json_feed")
      .querySelector("input")!;
    expect(radio).toBeDisabled();
  });

  it("FORMAT_OPTIONS has 3 entries", () => {
    expect(FORMAT_OPTIONS).toHaveLength(3);
  });

  it("highlights selected option with violet border", () => {
    render(
      <FormatSelector value="email" onChange={vi.fn()} isPro={true} />,
    );
    const emailOpt = screen.getByTestId("format-option-email");
    expect(emailOpt.className).toContain("border-violet-500");
  });
});
