"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function CheckEmailContent() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email") || "your email";
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  function handleResend() {
    setCooldown(60);
    // Re-trigger magic link via NextAuth
    fetch("/api/auth/signin/email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md text-center space-y-4">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-violet-100">
          <svg
            className="h-8 w-8 text-violet-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-semibold">Check your inbox</h1>

        <p className="text-gray-500">
          We sent a magic link to <strong>{email}</strong>. Click it to sign in.
        </p>

        <button
          onClick={handleResend}
          disabled={cooldown > 0}
          className="text-sm text-violet-600 hover:underline disabled:text-gray-400 disabled:no-underline"
        >
          {cooldown > 0
            ? `Resend in ${cooldown}s`
            : "Didn\u2019t get it? Resend"}
        </button>
      </div>
    </main>
  );
}

export default function CheckEmailPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center px-4">
          <p className="text-gray-500">Loading...</p>
        </main>
      }
    >
      <CheckEmailContent />
    </Suspense>
  );
}
