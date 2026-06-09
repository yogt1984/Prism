import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Home, { FEATURES, STEPS } from "@/app/page";

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

describe("LandingPage", () => {
  it("renders the landing page wrapper", () => {
    render(<Home />);
    expect(screen.getByTestId("landing-page")).toBeInTheDocument();
  });

  it("displays the Prism wordmark", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Prism",
    );
  });

  it("displays the product motto", () => {
    render(<Home />);
    expect(
      screen.getByText(/make the bias transparent/),
    ).toBeInTheDocument();
  });

  it("renders hero signup link pointing to /signup", () => {
    render(<Home />);
    const link = screen.getByTestId("hero-signup-link");
    expect(link).toHaveAttribute("href", "/signup");
    expect(link).toHaveTextContent("Get started");
  });

  it("renders hero pricing link pointing to /pricing", () => {
    render(<Home />);
    const link = screen.getByTestId("hero-pricing-link");
    expect(link).toHaveAttribute("href", "/pricing");
    expect(link).toHaveTextContent("See pricing");
  });

  it("renders all six feature items", () => {
    render(<Home />);
    expect(screen.getByTestId("features-section")).toBeInTheDocument();
    for (const f of FEATURES) {
      expect(screen.getByText(f.title)).toBeInTheDocument();
    }
  });

  it("renders features section heading", () => {
    render(<Home />);
    expect(
      screen.getByText("What Prism does differently"),
    ).toBeInTheDocument();
  });

  it("renders the how-it-works section with three steps", () => {
    render(<Home />);
    expect(screen.getByTestId("how-it-works-section")).toBeInTheDocument();
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByText("03")).toBeInTheDocument();
  });

  it("renders step titles", () => {
    render(<Home />);
    for (const s of STEPS) {
      expect(screen.getByText(s.title)).toBeInTheDocument();
    }
  });

  it("renders the philosophy quote", () => {
    render(<Home />);
    expect(screen.getByTestId("philosophy-section")).toBeInTheDocument();
    expect(
      screen.getByText(/optimizes for understanding/),
    ).toBeInTheDocument();
  });

  it("renders bottom CTA with signup link", () => {
    render(<Home />);
    const link = screen.getByTestId("bottom-signup-link");
    expect(link).toHaveAttribute("href", "/signup");
    expect(link).toHaveTextContent("Create your account");
  });

  it("renders bottom CTA with pricing link", () => {
    render(<Home />);
    const link = screen.getByTestId("bottom-pricing-link");
    expect(link).toHaveAttribute("href", "/pricing");
    expect(link).toHaveTextContent("Compare plans");
  });

  it("shows free plan notice in bottom CTA", () => {
    render(<Home />);
    expect(
      screen.getByText(/No credit card required/),
    ).toBeInTheDocument();
  });

  it("renders the footer", () => {
    render(<Home />);
    expect(screen.getByTestId("landing-footer")).toBeInTheDocument();
  });

  it("exports FEATURES with 6 items", () => {
    expect(FEATURES).toHaveLength(6);
  });

  it("exports STEPS with 3 items", () => {
    expect(STEPS).toHaveLength(3);
  });
});
