import { describe, it, expect, vi, beforeEach } from "vitest";
import { authOptions, fetchUserByEmail } from "@/lib/auth";

// Mock global fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

const MOCK_USER = {
  id: 5,
  email: "test@example.com",
  api_key_hash: "abc123hash",
  is_pro: false,
  interests: "finance,technology",
};

describe("fetchUserByEmail", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("returns user when API returns valid response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [MOCK_USER],
    });

    const user = await fetchUserByEmail("test@example.com");
    expect(user).toEqual(MOCK_USER);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/users?email=test%40example.com"),
    );
  });

  it("returns user when API returns single object", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => MOCK_USER,
    });

    const user = await fetchUserByEmail("test@example.com");
    expect(user).toEqual(MOCK_USER);
  });

  it("returns null when API returns 404", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Not found" }),
    });

    const user = await fetchUserByEmail("nobody@example.com");
    expect(user).toBeNull();
  });

  it("returns null when API returns empty array", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    const user = await fetchUserByEmail("nobody@example.com");
    expect(user).toBeNull();
  });

  it("returns null on fetch error", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    const user = await fetchUserByEmail("test@example.com");
    expect(user).toBeNull();
  });

  it("encodes email in URL", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    await fetchUserByEmail("user+tag@example.com");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("user%2Btag%40example.com"),
    );
  });
});

describe("authOptions callbacks", () => {
  const callbacks = authOptions.callbacks!;

  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe("signIn", () => {
    it("allows sign-in for existing user", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [MOCK_USER],
      });

      const result = await callbacks.signIn!({
        user: { id: "1", email: "test@example.com" },
        account: null as never,
        profile: undefined,
        email: undefined,
        credentials: undefined,
      });

      expect(result).toBe(true);
    });

    it("blocks sign-in for unknown email", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Not found" }),
      });

      const result = await callbacks.signIn!({
        user: { id: "1", email: "nobody@example.com" },
        account: null as never,
        profile: undefined,
        email: undefined,
        credentials: undefined,
      });

      expect(result).toBe(false);
    });

    it("blocks sign-in when email is missing", async () => {
      const result = await callbacks.signIn!({
        user: { id: "1" },
        account: null as never,
        profile: undefined,
        email: undefined,
        credentials: undefined,
      });

      expect(result).toBe(false);
    });
  });

  describe("jwt", () => {
    it("embeds user data on signIn trigger", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [MOCK_USER],
      });

      const token = await callbacks.jwt!({
        token: { email: "test@example.com" },
        trigger: "signIn",
        user: {} as never,
        account: null,
        session: undefined,
      });

      expect(token.userId).toBe(5);
      expect(token.apiKeyHash).toBe("abc123hash");
      expect(token.isPro).toBe(false);
      expect(token.interests).toBe("finance,technology");
    });

    it("passes through token on non-signIn trigger", async () => {
      const token = await callbacks.jwt!({
        token: { email: "test@example.com", userId: 5 },
        trigger: "update",
        user: {} as never,
        account: null,
        session: undefined,
      });

      expect(token.userId).toBe(5);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("handles missing user gracefully on signIn", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

      const token = await callbacks.jwt!({
        token: { email: "nobody@example.com" },
        trigger: "signIn",
        user: {} as never,
        account: null,
        session: undefined,
      });

      expect(token.userId).toBeUndefined();
    });
  });

  describe("session", () => {
    it("exposes safe fields to session.user", async () => {
      const session = {
        user: { name: "Test", email: "test@example.com" },
        expires: "2099-01-01",
      };

      const result = await callbacks.session!({
        session,
        token: {
          userId: 5,
          isPro: true,
          interests: "finance",
          apiKeyHash: "secret",
        },
        trigger: "update",
        newSession: undefined,
      });

      expect((result.user as Record<string, unknown>).id).toBe(5);
      expect((result.user as Record<string, unknown>).isPro).toBe(true);
      expect((result.user as Record<string, unknown>).interests).toBe(
        "finance",
      );
      // api key must NOT leak
      expect((result.user as Record<string, unknown>).apiKeyHash).toBeUndefined();
    });

    it("handles missing user in session", async () => {
      const session = { user: undefined, expires: "2099-01-01" };
      const result = await callbacks.session!({
        session: session as never,
        token: { userId: 5 },
        trigger: "update",
        newSession: undefined,
      });
      expect(result).toBeDefined();
    });
  });
});

describe("authOptions config", () => {
  it("uses JWT session strategy", () => {
    expect(authOptions.session?.strategy).toBe("jwt");
  });

  it("session maxAge is 30 days", () => {
    expect(authOptions.session?.maxAge).toBe(30 * 24 * 60 * 60);
  });

  it("custom pages are configured", () => {
    expect(authOptions.pages?.signIn).toBe("/login");
    expect(authOptions.pages?.newUser).toBe("/signup");
    expect(authOptions.pages?.verifyRequest).toBe("/check-email");
    expect(authOptions.pages?.error).toBe("/auth-error");
  });

  it("uses email provider", () => {
    expect(authOptions.providers).toHaveLength(1);
    expect(authOptions.providers[0].id).toBe("email");
  });
});
