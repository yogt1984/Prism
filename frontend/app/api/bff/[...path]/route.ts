import { getServerSession } from "next-auth";
import { getToken } from "next-auth/jwt";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { authOptions } from "@/lib/auth";

const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000";

async function proxyToFastAPI(request: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const token = await getToken({ req: request });
  if (!token?.apiKeyHash) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Strip the /api/bff/ prefix to get the FastAPI path
  const path = request.nextUrl.pathname.replace("/api/bff/", "");
  const search = request.nextUrl.search;
  const url = `${FASTAPI_URL}/${path}${search}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-API-Key": token.apiKeyHash as string,
  };

  // Forward Range header for audio seeking
  const rangeHeader = request.headers.get("range");
  if (rangeHeader) {
    headers["Range"] = rangeHeader;
  }

  const fetchOptions: RequestInit = {
    method: request.method,
    headers,
  };

  if (!["GET", "HEAD"].includes(request.method)) {
    fetchOptions.body = await request.text();
  }

  try {
    const res = await fetch(url, fetchOptions);

    // Stream binary audio responses directly
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("audio/")) {
      const responseHeaders: Record<string, string> = {
        "Content-Type": contentType,
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=86400",
      };
      const contentLength = res.headers.get("content-length");
      if (contentLength) responseHeaders["Content-Length"] = contentLength;
      const contentRange = res.headers.get("content-range");
      if (contentRange) responseHeaders["Content-Range"] = contentRange;
      const contentDisposition = res.headers.get("content-disposition");
      if (contentDisposition)
        responseHeaders["Content-Disposition"] = contentDisposition;

      return new NextResponse(res.body, {
        status: res.status,
        headers: responseHeaders,
      });
    }

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 },
    );
  }
}

export {
  proxyToFastAPI as GET,
  proxyToFastAPI as POST,
  proxyToFastAPI as PATCH,
  proxyToFastAPI as DELETE,
};
