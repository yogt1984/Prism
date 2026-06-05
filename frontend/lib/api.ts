/** Typed fetch helpers for BFF API calls. */

const API_BASE = "/api/bff";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail || "Request failed");
  }

  return res.json();
}

export interface SignupPayload {
  email: string;
  interests: string[];
}

export async function signup(payload: SignupPayload) {
  return apiFetch<{ id: number; email: string }>("/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
