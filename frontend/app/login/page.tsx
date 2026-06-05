"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";
import Link from "next/link";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const trimmed = email.toLowerCase().trim();
    if (!EMAIL_RE.test(trimmed)) {
      setError("Enter a valid email");
      return;
    }

    setLoading(true);
    try {
      const result = await signIn("email", {
        email: trimmed,
        callbackUrl: "/dashboard",
        redirect: false,
      });

      if (result?.error) {
        setError("Could not send magic link. Try again.");
      } else {
        window.location.href = "/check-email";
      }
    } catch {
      setError("Service temporarily unavailable");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-semibold">Log in to Prism</h1>
          <p className="mt-2 text-sm text-gray-500">
            We&apos;ll send you a magic link to sign in.
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-gray-700"
            >
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
            />
            {error && (
              <p className="mt-1 text-sm text-red-600" role="alert">
                {error}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-violet-600 px-4 py-2 text-white font-medium hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Sending..." : "Send magic link"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500">
          New here?{" "}
          <Link href="/signup" className="text-violet-600 hover:underline">
            Create account
          </Link>
        </p>
      </div>
    </main>
  );
}
