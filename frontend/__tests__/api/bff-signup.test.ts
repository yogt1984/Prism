import { describe, it, expect, vi, beforeEach } from "vitest";
import { POST } from "@/app/api/bff/signup/route";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function makeRequest(body: object): Request {
  return new Request("http://localhost:3000/api/bff/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("POST /api/bff/signup", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("returns 201 on successful registration", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({
        id: 1,
        email: "test@example.com",
        interests: "finance,technology",
      }),
    });

    const res = await POST(
      makeRequest({ email: "test@example.com", interests: ["finance", "technology"] }),
    );

    expect(res.status).toBe(201);
    const data = await res.json();
    expect(data.id).toBe(1);
    expect(data.email).toBe("test@example.com");
  });

  it("forwards email in lowercase trimmed form", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 1, email: "test@example.com" }),
    });

    await POST(
      makeRequest({ email: "  TEST@Example.COM  ", interests: ["finance"] }),
    );

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.stringContaining('"test@example.com"'),
      }),
    );
  });

  it("joins interests with commas", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 1 }),
    });

    await POST(
      makeRequest({ email: "a@b.com", interests: ["finance", "sports"] }),
    );

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.stringContaining('"finance,sports"'),
      }),
    );
  });

  it("returns 400 for missing email", async () => {
    const res = await POST(
      makeRequest({ email: "", interests: ["finance"] }),
    );
    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.detail).toContain("email");
  });

  it("returns 400 for invalid email", async () => {
    const res = await POST(
      makeRequest({ email: "notanemail", interests: ["finance"] }),
    );
    expect(res.status).toBe(400);
  });

  it("returns 400 for empty interests", async () => {
    const res = await POST(
      makeRequest({ email: "a@b.com", interests: [] }),
    );
    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.detail).toContain("interest");
  });

  it("returns 422 for duplicate email from FastAPI", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Email already registered" }),
    });

    const res = await POST(
      makeRequest({ email: "dup@example.com", interests: ["finance"] }),
    );

    expect(res.status).toBe(422);
    const data = await res.json();
    expect(data.detail).toContain("Email already registered");
  });

  it("returns 503 when FastAPI is unreachable", async () => {
    mockFetch.mockRejectedValueOnce(new Error("ECONNREFUSED"));

    const res = await POST(
      makeRequest({ email: "a@b.com", interests: ["finance"] }),
    );

    expect(res.status).toBe(503);
    const data = await res.json();
    expect(data.detail).toContain("unavailable");
  });

  it("sets briefing_depth to 10", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 1 }),
    });

    await POST(
      makeRequest({ email: "a@b.com", interests: ["finance"] }),
    );

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.stringContaining('"briefing_depth":10'),
      }),
    );
  });

  it("passes correct URL and method to FastAPI", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 1 }),
    });

    await POST(
      makeRequest({ email: "a@b.com", interests: ["finance"] }),
    );

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/users"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
});
