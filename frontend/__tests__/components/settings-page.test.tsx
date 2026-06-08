import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SettingsPage, { setsEqual } from "@/app/settings/page";
import { createWrapper } from "../helpers/query-wrapper";
import type { User } from "@/lib/types";

const mockSearchParams = vi.hoisted(() => vi.fn(() => new URLSearchParams()));

vi.mock("next/navigation", () => ({
  useSearchParams: mockSearchParams,
}));

const mockSession = vi.hoisted(() =>
  vi.fn(() => ({
    data: {
      user: { id: 5, email: "user@test.com", name: "Test User" },
    },
    status: "authenticated",
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

describe("SettingsPage", () => {
  const user = makeUser();

  beforeEach(() => {
    mockFetch.mockImplementation((url: string, init?: RequestInit) => {
      if (
        url.includes("/users/5") &&
        (!init?.method || init.method === "GET")
      ) {
        return Promise.resolve(mockJsonResponse(user));
      }
      if (url.includes("/users/5") && init?.method === "PATCH") {
        const body = JSON.parse(init.body as string);
        return Promise.resolve(mockJsonResponse({ ...user, ...body }));
      }
      return Promise.resolve(mockJsonResponse({}, 404));
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<SettingsPage />, { wrapper: createWrapper() });
    expect(screen.getByTestId("settings-loading")).toBeInTheDocument();
  });

  it("renders settings page after load", async () => {
    render(<SettingsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("settings-page")).toBeInTheDocument();
    });
  });

  it("renders all sections", async () => {
    render(<SettingsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("profile-section")).toBeInTheDocument();
    });
    expect(screen.getByTestId("interests-section")).toBeInTheDocument();
    expect(screen.getByTestId("preferences-section")).toBeInTheDocument();
    expect(screen.getByTestId("subscription-section")).toBeInTheDocument();
    expect(screen.getByTestId("danger-zone")).toBeInTheDocument();
  });

  it("shows error state on fetch failure", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse({}, 500));
    render(<SettingsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("settings-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Could not load settings")).toBeInTheDocument();
  });

  describe("Profile section", () => {
    it("displays email as disabled", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("email-field")).toBeInTheDocument();
      });
      expect(screen.getByTestId("email-field")).toBeDisabled();
      expect(screen.getByTestId("email-field")).toHaveValue("user@test.com");
    });

    it("populates name field with user name", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("name-field")).toHaveValue("Jane");
      });
    });

    it("save button is disabled when name unchanged", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("settings-page")).toBeInTheDocument();
      });
      const saveButtons = screen.getAllByTestId("save-btn");
      expect(saveButtons[0]).toBeDisabled();
    });

    it("save button is enabled after name change", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("name-field")).toBeInTheDocument();
      });
      fireEvent.change(screen.getByTestId("name-field"), {
        target: { value: "Jane Doe" },
      });
      const saveButtons = screen.getAllByTestId("save-btn");
      expect(saveButtons[0]).not.toBeDisabled();
    });
  });

  describe("Interests section", () => {
    it("renders all 8 interest toggles", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(
          screen.getByTestId("interest-toggle-finance"),
        ).toBeInTheDocument();
      });
      expect(
        screen.getByTestId("interest-toggle-politics"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("interest-toggle-technology"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("interest-toggle-sports"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("interest-toggle-culture"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("interest-toggle-science"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("interest-toggle-health"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("interest-toggle-world"),
      ).toBeInTheDocument();
    });

    it("pre-selects user interests", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(
          screen.getByTestId("interest-toggle-finance"),
        ).toHaveAttribute("aria-pressed", "true");
      });
      expect(
        screen.getByTestId("interest-toggle-technology"),
      ).toHaveAttribute("aria-pressed", "true");
      expect(
        screen.getByTestId("interest-toggle-sports"),
      ).toHaveAttribute("aria-pressed", "false");
    });

    it("shows free tier notice for non-Pro users", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(
          screen.getByTestId("tier-notice-interests"),
        ).toBeInTheDocument();
      });
    });

    it("hides free tier notice for Pro users", async () => {
      const proUser = makeUser({ is_pro: true });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(proUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("settings-page")).toBeInTheDocument();
      });
      expect(
        screen.queryByTestId("tier-notice-interests"),
      ).not.toBeInTheDocument();
    });

    it("enables save after toggling an interest", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(
          screen.getByTestId("interest-toggle-sports"),
        ).toBeInTheDocument();
      });
      fireEvent.click(screen.getByTestId("interest-toggle-sports"));
      const saveButtons = screen.getAllByTestId("save-btn");
      // Interests save button is the second one
      expect(saveButtons[1]).not.toBeDisabled();
    });
  });

  describe("Preferences section", () => {
    it("renders format selector", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("format-selector")).toBeInTheDocument();
      });
    });

    it("renders depth slider", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("depth-slider")).toBeInTheDocument();
      });
    });

    it("sets depth slider max to 10 for free users", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("depth-range")).toHaveAttribute(
          "max",
          "10",
        );
      });
    });

    it("sets depth slider max to 25 for pro users", async () => {
      const proUser = makeUser({ is_pro: true });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(proUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("depth-range")).toHaveAttribute(
          "max",
          "25",
        );
      });
    });

    it("shows depth tier notice for free users", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(
          screen.getByTestId("tier-notice-depth"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Subscription section", () => {
    it("shows Free plan badge for non-Pro users", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("plan-badge")).toHaveTextContent("Free");
      });
    });

    it("shows Pro plan badge for Pro users", async () => {
      const proUser = makeUser({ is_pro: true, has_stripe_subscription: true });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(proUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("plan-badge")).toHaveTextContent("Pro");
      });
    });

    it("shows upgrade card with enabled button for free users", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("upgrade-card")).toBeInTheDocument();
      });
      expect(screen.getByTestId("upgrade-btn")).not.toBeDisabled();
    });

    it("hides upgrade card for pro users", async () => {
      const proUser = makeUser({ is_pro: true, has_stripe_subscription: true });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(proUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("settings-page")).toBeInTheDocument();
      });
      expect(screen.queryByTestId("upgrade-card")).not.toBeInTheDocument();
    });

    it("shows manage button for pro users", async () => {
      const proUser = makeUser({ is_pro: true, has_stripe_subscription: true });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(proUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("manage-btn")).toBeInTheDocument();
      });
    });

    it("hides manage button for free users", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("settings-page")).toBeInTheDocument();
      });
      expect(screen.queryByTestId("manage-btn")).not.toBeInTheDocument();
    });

    it("shows grace period warning for pro user with future pro_until", async () => {
      const graceUser = makeUser({
        is_pro: true,
        has_stripe_subscription: true,
        pro_until: "2099-01-01T00:00:00Z",
      });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(graceUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("grace-period-warning")).toBeInTheDocument();
      });
    });

    it("hides grace period warning when pro_until is null", async () => {
      const proUser = makeUser({ is_pro: true, has_stripe_subscription: true });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(proUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("settings-page")).toBeInTheDocument();
      });
      expect(screen.queryByTestId("grace-period-warning")).not.toBeInTheDocument();
    });

    it("shows resubscribe notice for expired user", async () => {
      const expiredUser = makeUser({
        is_pro: false,
        pro_until: "2024-01-01T00:00:00Z",
      });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(expiredUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("resubscribe-notice")).toBeInTheDocument();
      });
    });

    it("shows success banner when upgraded=true in URL", async () => {
      mockSearchParams.mockReturnValue(new URLSearchParams("upgraded=true"));
      const proUser = makeUser({ is_pro: true, has_stripe_subscription: true });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(proUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("success-banner")).toBeInTheDocument();
      });
      mockSearchParams.mockReturnValue(new URLSearchParams());
    });

    it("shows cancelled notice when upgrade_cancelled=true in URL", async () => {
      mockSearchParams.mockReturnValue(
        new URLSearchParams("upgrade_cancelled=true"),
      );

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("cancelled-notice")).toBeInTheDocument();
      });
      expect(screen.getByText(/cancelled/i)).toBeInTheDocument();
      mockSearchParams.mockReturnValue(new URLSearchParams());
    });

    it("shows pro_since date for pro users", async () => {
      const proUser = makeUser({
        is_pro: true,
        has_stripe_subscription: true,
        pro_since: "2026-03-15T00:00:00Z",
      });
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/users/5")) {
          return Promise.resolve(mockJsonResponse(proUser));
        }
        return Promise.resolve(mockJsonResponse({}, 404));
      });

      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("pro-since")).toBeInTheDocument();
      });
    });

    it("renders feature comparison table", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(
          screen.getByTestId("feature-comparison"),
        ).toBeInTheDocument();
      });
      expect(screen.getAllByTestId("comparison-row")).toHaveLength(6);
    });
  });

  describe("Danger Zone", () => {
    it("renders delete account button (disabled)", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(
          screen.getByTestId("delete-account-btn"),
        ).toBeInTheDocument();
      });
      expect(screen.getByTestId("delete-account-btn")).toBeDisabled();
    });
  });

  describe("Save mutations", () => {
    it("sends PATCH with name on profile save", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(screen.getByTestId("name-field")).toHaveValue("Jane");
      });

      fireEvent.change(screen.getByTestId("name-field"), {
        target: { value: "Jane Doe" },
      });
      const saveButtons = screen.getAllByTestId("save-btn");
      fireEvent.click(saveButtons[0]);

      await waitFor(() => {
        const patchCalls = mockFetch.mock.calls.filter(
          ([, init]) =>
            init &&
            typeof init === "object" &&
            "method" in init &&
            init.method === "PATCH",
        );
        expect(patchCalls.length).toBeGreaterThanOrEqual(1);
      });
    });

    it("sends PATCH with interests on interests save", async () => {
      render(<SettingsPage />, { wrapper: createWrapper() });
      await waitFor(() => {
        expect(
          screen.getByTestId("interest-toggle-sports"),
        ).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("interest-toggle-sports"));
      const saveButtons = screen.getAllByTestId("save-btn");
      fireEvent.click(saveButtons[1]);

      await waitFor(() => {
        const patchCalls = mockFetch.mock.calls.filter(
          ([, init]) =>
            init &&
            typeof init === "object" &&
            "method" in init &&
            init.method === "PATCH",
        );
        expect(patchCalls.length).toBeGreaterThanOrEqual(1);
      });
    });
  });
});

describe("setsEqual", () => {
  it("returns true for equal sets", () => {
    expect(setsEqual(new Set(["a", "b"]), new Set(["a", "b"]))).toBe(true);
  });

  it("returns false for different sizes", () => {
    expect(setsEqual(new Set(["a"]), new Set(["a", "b"]))).toBe(false);
  });

  it("returns false for different values", () => {
    expect(setsEqual(new Set(["a", "b"]), new Set(["a", "c"]))).toBe(
      false,
    );
  });

  it("returns true for empty sets", () => {
    expect(setsEqual(new Set(), new Set())).toBe(true);
  });
});
