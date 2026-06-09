import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PricingPage, { TIERS } from "@/app/pricing/page";
import { createWrapper } from "../helpers/query-wrapper";
import type { User } from "@/lib/types";

const mockSession = vi.hoisted(() =>
  vi.fn(() => ({
    data: null,
    status: "unauthenticated",
  })),
);

vi.mock("next-auth/react", () => ({
  useSession: mockSession,
}));

const mockFetch = vi.hoisted(() => vi.fn<(url: string, init?: RequestInit) => Promise<Response>>());
vi.stubGlobal("fetch", mockFetch);

function mockJsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers({ "content-type": "application/json" }),
  } as Response;
}

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 5,
    email: "user@test.com",
    name: "Jane",
    interests: "finance,technology",
    preferred_format: "email",
    briefing_depth: 10,
    is_pro: false,
    pro_since: null,
    pro_until: null,
    has_stripe_subscription: false,
    created_at: "2026-05-15T10:00:00Z",
    ...overrides,
  };
}

function setSession(opts: { authenticated: boolean; userId?: number }) {
  if (opts.authenticated) {
    mockSession.mockReturnValue({
      data: {
        user: { id: opts.userId ?? 5, email: "user@test.com", name: "Jane" },
      },
      status: "authenticated",
    });
  } else {
    mockSession.mockReturnValue({ data: null, status: "unauthenticated" });
  }
}

describe("PricingPage", () => {
  beforeEach(() => {
    mockFetch.mockImplementation(() => Promise.resolve(mockJsonResponse({}, 404)));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("unauthenticated user", () => {
    beforeEach(() => {
      setSession({ authenticated: false });
    });

    it("renders the pricing page", () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      expect(screen.getByTestId("pricing-page")).toBeInTheDocument();
    });

    it("renders both tier cards", () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      expect(screen.getByTestId("tier-free")).toBeInTheDocument();
      expect(screen.getByTestId("tier-pro")).toBeInTheDocument();
    });

    it("shows heading and description", () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      expect(screen.getByText("Simple, transparent pricing")).toBeInTheDocument();
      expect(screen.getByText(/No ads\. No data selling/)).toBeInTheDocument();
    });

    it("shows Sign Up Free button on free tier", () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      expect(screen.getByTestId("signup-free-link")).toBeInTheDocument();
      expect(screen.getByText("Sign Up Free")).toBeInTheDocument();
    });

    it("shows Get Started button on pro tier", () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      expect(screen.getByTestId("signup-link")).toBeInTheDocument();
      expect(screen.getByText("Get Started")).toBeInTheDocument();
    });

    it("does not show current plan badge", () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      expect(screen.queryByTestId("current-plan-badge")).not.toBeInTheDocument();
    });

    it("renders pricing footer with settings link", () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      expect(screen.getByTestId("pricing-footer")).toBeInTheDocument();
      expect(screen.getByText(/Cancel anytime/)).toBeInTheDocument();
    });
  });

  describe("authenticated free user", () => {
    const freeUser = makeUser();

    beforeEach(() => {
      setSession({ authenticated: true });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(freeUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });
    });

    it("shows current plan badge on free tier", async () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("current-plan-badge")).toBeInTheDocument();
      });
      expect(screen.getByText("Current plan")).toBeInTheDocument();
    });

    it("shows 'Your current plan' text on free tier", async () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("free-current")).toBeInTheDocument();
      });
    });

    it("shows Upgrade to Pro button on pro tier", async () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("upgrade-btn")).toBeInTheDocument();
      });
      expect(screen.getByText("Upgrade to Pro")).toBeInTheDocument();
    });

    it("does not show signup links", async () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("upgrade-btn")).toBeInTheDocument();
      });
      expect(screen.queryByTestId("signup-link")).not.toBeInTheDocument();
      expect(screen.queryByTestId("signup-free-link")).not.toBeInTheDocument();
    });

    it("upgrade button is not disabled", async () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("upgrade-btn")).toBeInTheDocument();
      });
      expect(screen.getByTestId("upgrade-btn")).not.toBeDisabled();
    });
  });

  describe("authenticated pro user", () => {
    const proUser = makeUser({ is_pro: true, has_stripe_subscription: true });

    beforeEach(() => {
      setSession({ authenticated: true });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(proUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });
    });

    it("shows current plan badge on pro tier", async () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("current-plan-badge")).toBeInTheDocument();
      });
    });

    it("shows Manage Subscription link on pro tier", async () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("manage-link")).toBeInTheDocument();
      });
      expect(screen.getByText("Manage Subscription")).toBeInTheDocument();
    });

    it("does not show upgrade button", async () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("manage-link")).toBeInTheDocument();
      });
      expect(screen.queryByTestId("upgrade-btn")).not.toBeInTheDocument();
    });

    it("does not show free-current text", async () => {
      render(<PricingPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("manage-link")).toBeInTheDocument();
      });
      expect(screen.queryByTestId("free-current")).not.toBeInTheDocument();
    });
  });

  describe("tier data", () => {
    it("exports TIERS constant with Free and Pro", () => {
      expect(TIERS).toHaveLength(2);
      expect(TIERS[0].name).toBe("Free");
      expect(TIERS[1].name).toBe("Pro");
    });

    it("Free tier has $0 price", () => {
      expect(TIERS[0].price).toBe("$0");
    });

    it("Pro tier has $7 price", () => {
      expect(TIERS[1].price).toBe("$7");
    });

    it("Pro tier features are all included", () => {
      expect(TIERS[1].features.every((f) => f.included)).toBe(true);
    });

    it("Free tier has some excluded features", () => {
      expect(TIERS[0].features.some((f) => !f.included)).toBe(true);
    });
  });
});
