"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";
import Link from "next/link";
import { CATEGORIES } from "@/lib/types";
import type { Category } from "@/lib/types";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const CATEGORY_LABELS: Record<Category, string> = {
  finance: "Finance",
  politics: "Politics",
  technology: "Technology",
  sports: "Sports",
  culture: "Culture",
  science: "Science",
  health: "Health",
  world: "World",
};

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [interests, setInterests] = useState<Category[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function toggleInterest(cat: Category) {
    setInterests((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat],
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const trimmed = email.toLowerCase().trim();
    if (!EMAIL_RE.test(trimmed)) {
      setError("Enter a valid email");
      return;
    }

    if (interests.length === 0) {
      setError("Select at least one interest");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/bff/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed, interests }),
      });

      if (res.status === 422) {
        setError("Account exists \u2014 log in instead");
        setLoading(false);
        return;
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Registration failed");
        setLoading(false);
        return;
      }

      // Account created — send magic link
      await signIn("email", {
        email: trimmed,
        callbackUrl: "/dashboard",
        redirect: false,
      });

      window.location.href = "/check-email";
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
          <h1 className="text-2xl font-semibold">Create your Prism account</h1>
          <p className="mt-2 text-sm text-gray-500">
            Choose your interests and we&apos;ll curate your news.
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
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Interests (select at least 1)
            </label>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => toggleInterest(cat)}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium border transition-colors ${
                    interests.includes(cat)
                      ? "bg-violet-600 text-white border-violet-600"
                      : "bg-white text-gray-700 border-gray-300 hover:border-violet-400"
                  }`}
                  role="checkbox"
                  aria-checked={interests.includes(cat)}
                  aria-label={CATEGORY_LABELS[cat]}
                >
                  {CATEGORY_LABELS[cat]}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-violet-600 px-4 py-2 text-white font-medium hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500">
          Already have an account?{" "}
          <Link href="/login" className="text-violet-600 hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </main>
  );
}
