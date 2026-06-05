import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("next-auth/jwt", () => ({
  getToken: vi.fn(),
}));

import { getToken } from "next-auth/jwt";
import { proxy, config } from "@/proxy";
import { NextRequest } from "next/server";

function makeRequest(path: string): NextRequest {
  return new NextRequest(`http://localhost:3000${path}`);
}

describe("proxy (route protection)", () => {
  beforeEach(() => {
    vi.mocked(getToken).mockReset();
  });

  it("redirects to /login when no token", async () => {
    vi.mocked(getToken).mockResolvedValueOnce(null);

    const res = await proxy(makeRequest("/dashboard"));

    expect(res.status).toBe(307);
    const location = res.headers.get("location");
    expect(location).toContain("/login");
    expect(location).toContain("callbackUrl=%2Fdashboard");
  });

  it("allows request when token exists", async () => {
    vi.mocked(getToken).mockResolvedValueOnce({
      email: "test@example.com",
      userId: 5,
    });

    const res = await proxy(makeRequest("/dashboard"));

    // NextResponse.next() returns 200
    expect(res.status).toBe(200);
  });

  it("includes callbackUrl in redirect", async () => {
    vi.mocked(getToken).mockResolvedValueOnce(null);

    const res = await proxy(makeRequest("/stories/42"));

    const location = res.headers.get("location");
    expect(location).toContain("callbackUrl=%2Fstories%2F42");
  });
});

describe("proxy config matcher", () => {
  it("matches protected routes", () => {
    const matchers = config.matcher;
    expect(matchers).toContain("/dashboard/:path*");
    expect(matchers).toContain("/stories/:path*");
    expect(matchers).toContain("/briefings/:path*");
    expect(matchers).toContain("/perception/:path*");
    expect(matchers).toContain("/settings/:path*");
    expect(matchers).toContain("/sources/:path*");
    expect(matchers).toContain("/api/bff/:path*");
  });

  it("has 7 matcher patterns", () => {
    expect(config.matcher).toHaveLength(7);
  });

  it("does not include public routes", () => {
    const matchers = config.matcher;
    expect(matchers).not.toContain("/");
    expect(matchers).not.toContain("/login");
    expect(matchers).not.toContain("/signup");
    expect(matchers).not.toContain("/check-email");
    expect(matchers).not.toContain("/auth-error");
  });
});
