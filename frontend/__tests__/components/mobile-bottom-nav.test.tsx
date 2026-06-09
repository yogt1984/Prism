import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import MobileBottomNav, {
  NAV_ITEMS,
  HIDDEN_ROUTES,
  isActive,
} from "@/components/navigation/MobileBottomNav";

let mockPathname = "/dashboard";
let mockSessionStatus = "authenticated";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({ status: mockSessionStatus }),
}));

describe("isActive", () => {
  it("matches exact path", () => {
    expect(isActive("/briefings", "/briefings")).toBe(true);
  });

  it("matches child path", () => {
    expect(isActive("/briefings/42", "/briefings")).toBe(true);
  });

  it("does not match unrelated path", () => {
    expect(isActive("/sources", "/briefings")).toBe(false);
  });

  it("does not match partial prefix", () => {
    expect(isActive("/settings-extra", "/settings")).toBe(false);
  });
});

describe("MobileBottomNav", () => {
  beforeEach(() => {
    mockPathname = "/dashboard";
    mockSessionStatus = "authenticated";
  });

  it("renders all 5 nav items when authenticated", () => {
    render(<MobileBottomNav />);
    expect(screen.getByTestId("mobile-bottom-nav")).toBeInTheDocument();
    for (const item of NAV_ITEMS) {
      expect(
        screen.getByTestId(`bottom-nav-${item.label.toLowerCase()}`),
      ).toBeInTheDocument();
    }
  });

  it("each nav item links to correct href", () => {
    render(<MobileBottomNav />);
    for (const item of NAV_ITEMS) {
      const link = screen.getByTestId(`bottom-nav-${item.label.toLowerCase()}`);
      expect(link).toHaveAttribute("href", item.href);
    }
  });

  it("highlights active item for current route", () => {
    mockPathname = "/briefings";
    render(<MobileBottomNav />);
    const active = screen.getByTestId("bottom-nav-briefings");
    expect(active).toHaveAttribute("aria-current", "page");
    expect(active.className).toContain("text-violet-600");
  });

  it("does not highlight inactive items", () => {
    mockPathname = "/briefings";
    render(<MobileBottomNav />);
    const inactive = screen.getByTestId("bottom-nav-sources");
    expect(inactive).not.toHaveAttribute("aria-current");
    expect(inactive.className).toContain("text-gray-500");
  });

  it("highlights parent route for child paths", () => {
    mockPathname = "/briefings/42";
    render(<MobileBottomNav />);
    const active = screen.getByTestId("bottom-nav-briefings");
    expect(active).toHaveAttribute("aria-current", "page");
  });

  it("does not render when unauthenticated", () => {
    mockSessionStatus = "unauthenticated";
    render(<MobileBottomNav />);
    expect(screen.queryByTestId("mobile-bottom-nav")).not.toBeInTheDocument();
  });

  it("does not render during loading", () => {
    mockSessionStatus = "loading";
    render(<MobileBottomNav />);
    expect(screen.queryByTestId("mobile-bottom-nav")).not.toBeInTheDocument();
  });

  it.each(["/login", "/signup", "/check-email", "/auth-error", "/"])(
    "does not render on %s",
    (route) => {
      mockPathname = route;
      render(<MobileBottomNav />);
      expect(screen.queryByTestId("mobile-bottom-nav")).not.toBeInTheDocument();
    },
  );

  it("has lg:hidden class for desktop hiding", () => {
    render(<MobileBottomNav />);
    const nav = screen.getByTestId("mobile-bottom-nav");
    expect(nav.className).toContain("lg:hidden");
  });

  it("renders nav labels as text", () => {
    render(<MobileBottomNav />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Briefings")).toBeInTheDocument();
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("Perception")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });
});

describe("NAV_ITEMS", () => {
  it("has 5 items", () => {
    expect(NAV_ITEMS).toHaveLength(5);
  });
});

describe("HIDDEN_ROUTES", () => {
  it("includes auth pages, root, and pricing", () => {
    expect(HIDDEN_ROUTES).toContain("/login");
    expect(HIDDEN_ROUTES).toContain("/signup");
    expect(HIDDEN_ROUTES).toContain("/check-email");
    expect(HIDDEN_ROUTES).toContain("/auth-error");
    expect(HIDDEN_ROUTES).toContain("/");
    expect(HIDDEN_ROUTES).toContain("/pricing");
  });
});
