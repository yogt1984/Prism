import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiFetch, ApiError, signup } from "@/lib/api";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("ApiError", () => {
  it("stores status and message", () => {
    const err = new ApiError(404, "Not found");
    expect(err.status).toBe(404);
    expect(err.message).toBe("Not found");
    expect(err.name).toBe("ApiError");
  });

  it("is an instance of Error", () => {
    const err = new ApiError(500, "Server error");
    expect(err).toBeInstanceOf(Error);
  });
});

describe("apiFetch", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("makes GET request to BFF path", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: 1, headline: "Test" }],
    });

    const data = await apiFetch("/stories");

    expect(mockFetch).toHaveBeenCalledWith("/api/bff/stories", {
      headers: { "Content-Type": "application/json" },
    });
    expect(data).toEqual([{ id: 1, headline: "Test" }]);
  });

  it("passes custom options through", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1 }),
    });

    await apiFetch("/users", {
      method: "POST",
      body: JSON.stringify({ email: "test@example.com" }),
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/bff/users",
      expect.objectContaining({
        method: "POST",
        body: '{"email":"test@example.com"}',
      }),
    );
  });

  it("throws ApiError on non-ok response with detail", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Duplicate email" }),
    });

    await expect(apiFetch("/users")).rejects.toThrow(ApiError);

    try {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Duplicate email" }),
      });
      await apiFetch("/users");
    } catch (err) {
      expect((err as ApiError).status).toBe(422);
      expect((err as ApiError).message).toBe("Duplicate email");
    }
  });

  it("throws ApiError with fallback message when no detail", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    try {
      await apiFetch("/fail");
    } catch (err) {
      expect((err as ApiError).message).toBe("Request failed");
    }
  });

  it("throws ApiError when json parsing fails", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("bad json");
      },
    });

    try {
      await apiFetch("/fail");
    } catch (err) {
      expect((err as ApiError).status).toBe(500);
      expect((err as ApiError).message).toBe("Request failed");
    }
  });

  it("merges additional headers", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    await apiFetch("/test", {
      headers: { "X-Custom": "value" },
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/bff/test",
      expect.objectContaining({
        headers: {
          "Content-Type": "application/json",
          "X-Custom": "value",
        },
      }),
    );
  });
});

describe("signup", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("sends POST to /api/bff/signup", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1, email: "test@example.com" }),
    });

    const result = await signup({
      email: "test@example.com",
      interests: ["finance", "technology"],
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/bff/signup",
      expect.objectContaining({
        method: "POST",
        body: '{"email":"test@example.com","interests":["finance","technology"]}',
      }),
    );
    expect(result).toEqual({ id: 1, email: "test@example.com" });
  });

  it("throws ApiError on failure", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Duplicate" }),
    });

    await expect(
      signup({ email: "test@example.com", interests: ["finance"] }),
    ).rejects.toThrow(ApiError);
  });
});
