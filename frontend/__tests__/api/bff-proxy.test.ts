import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock next-auth before imports
vi.mock("next-auth", () => ({
  getServerSession: vi.fn(),
}));
vi.mock("next-auth/jwt", () => ({
  getToken: vi.fn(),
}));
vi.mock("@/lib/auth", () => ({
  authOptions: {},
}));

import { getServerSession } from "next-auth";
import { getToken } from "next-auth/jwt";

// Import after mocking
const { GET, POST, PATCH, DELETE } = await import(
  "@/app/api/bff/[...path]/route"
);

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function makeRequest(
  path: string,
  method: string = "GET",
  body?: string,
): Request & { nextUrl: { pathname: string; search: string } } {
  const req = new Request(`http://localhost:3000/api/bff/${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body,
  });
  // Next.js adds nextUrl
  (req as Record<string, unknown>).nextUrl = {
    pathname: `/api/bff/${path}`,
    search: "",
  };
  return req as Request & { nextUrl: { pathname: string; search: string } };
}

describe("BFF proxy", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    vi.mocked(getServerSession).mockReset();
    vi.mocked(getToken).mockReset();
  });

  it("returns 401 when no session", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce(null);

    const res = await GET(makeRequest("stories"));
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.error).toBe("Unauthorized");
  });

  it("returns 401 when session exists but no apiKeyHash in token", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce({
      user: { email: "test@example.com" },
    });
    vi.mocked(getToken).mockResolvedValueOnce({ email: "test@example.com" });

    const res = await GET(makeRequest("stories"));
    expect(res.status).toBe(401);
  });

  it("proxies GET to FastAPI with X-API-Key header", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce({
      user: { email: "test@example.com" },
    });
    vi.mocked(getToken).mockResolvedValueOnce({
      email: "test@example.com",
      apiKeyHash: "key_abc123",
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [{ id: 1, headline: "News" }],
    });

    const res = await GET(makeRequest("stories"));

    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/stories"),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          "X-API-Key": "key_abc123",
        }),
      }),
    );
  });

  it("proxies POST with body", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce({
      user: { email: "test@example.com" },
    });
    vi.mocked(getToken).mockResolvedValueOnce({
      apiKeyHash: "key_abc123",
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 1 }),
    });

    const res = await POST(
      makeRequest("engagements", "POST", '{"action":"read"}'),
    );

    expect(res.status).toBe(201);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: "POST",
        body: '{"action":"read"}',
      }),
    );
  });

  it("proxies PATCH requests", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce({
      user: { email: "test@example.com" },
    });
    vi.mocked(getToken).mockResolvedValueOnce({
      apiKeyHash: "key_abc123",
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ id: 5 }),
    });

    const res = await PATCH(
      makeRequest("users/5", "PATCH", '{"name":"New Name"}'),
    );

    expect(res.status).toBe(200);
  });

  it("proxies DELETE requests", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce({
      user: { email: "test@example.com" },
    });
    vi.mocked(getToken).mockResolvedValueOnce({
      apiKeyHash: "key_abc123",
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });

    const res = await DELETE(makeRequest("keywords/3", "DELETE"));
    expect(res.status).toBe(200);
  });

  it("forwards query string", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce({
      user: { email: "test@example.com" },
    });
    vi.mocked(getToken).mockResolvedValueOnce({
      apiKeyHash: "key_abc123",
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [],
    });

    const req = makeRequest("stories");
    req.nextUrl.search = "?limit=10&offset=0";
    await GET(req);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("?limit=10&offset=0"),
      expect.anything(),
    );
  });

  it("forwards error status from FastAPI", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce({
      user: { email: "test@example.com" },
    });
    vi.mocked(getToken).mockResolvedValueOnce({
      apiKeyHash: "key_abc123",
    });
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Not found" }),
    });

    const res = await GET(makeRequest("stories/999"));
    expect(res.status).toBe(404);
  });

  it("returns 502 when backend is unreachable", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce({
      user: { email: "test@example.com" },
    });
    vi.mocked(getToken).mockResolvedValueOnce({
      apiKeyHash: "key_abc123",
    });
    mockFetch.mockRejectedValueOnce(new Error("ECONNREFUSED"));

    const res = await GET(makeRequest("stories"));
    expect(res.status).toBe(502);
    const data = await res.json();
    expect(data.error).toContain("unavailable");
  });

  it("does not send body on GET requests", async () => {
    vi.mocked(getServerSession).mockResolvedValueOnce({
      user: { email: "test@example.com" },
    });
    vi.mocked(getToken).mockResolvedValueOnce({
      apiKeyHash: "key_abc123",
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [],
    });

    await GET(makeRequest("stories"));

    const callArgs = mockFetch.mock.calls[0][1];
    expect(callArgs.body).toBeUndefined();
  });
});
