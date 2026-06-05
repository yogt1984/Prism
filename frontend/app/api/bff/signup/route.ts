import { NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { email, interests } = body as {
      email: string;
      interests: string[];
    };

    if (!email || !email.includes("@")) {
      return NextResponse.json(
        { detail: "Enter a valid email" },
        { status: 400 },
      );
    }

    if (!interests || interests.length === 0) {
      return NextResponse.json(
        { detail: "Select at least one interest" },
        { status: 400 },
      );
    }

    const res = await fetch(`${FASTAPI_URL}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email.toLowerCase().trim(),
        interests: interests.join(","),
        briefing_depth: 10,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      const status = res.status === 422 ? 422 : res.status;
      return NextResponse.json(
        { detail: data.detail || "Registration failed" },
        { status },
      );
    }

    return NextResponse.json(data, { status: 201 });
  } catch {
    return NextResponse.json(
      { detail: "Service temporarily unavailable" },
      { status: 503 },
    );
  }
}
