"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";

interface ErrorInfo {
  title: string;
  description: string;
  action: { label: string; href: string };
}

const ERROR_MAP: Record<string, ErrorInfo> = {
  EmailSignin: {
    title: "Could not send magic link",
    description:
      "There was a problem sending the sign-in email. Please try again.",
    action: { label: "Try again", href: "/login" },
  },
  Verification: {
    title: "Link expired or already used",
    description: "Magic links are single-use and expire after 24 hours.",
    action: { label: "Request new link", href: "/login" },
  },
  AccessDenied: {
    title: "No account found",
    description:
      "There is no Prism account associated with this email address.",
    action: { label: "Create account", href: "/signup" },
  },
};

const DEFAULT_ERROR: ErrorInfo = {
  title: "Something went wrong",
  description: "An unexpected error occurred during authentication.",
  action: { label: "Back to login", href: "/login" },
};

function AuthErrorContent() {
  const searchParams = useSearchParams();
  const errorCode = searchParams.get("error") || "";
  const info = ERROR_MAP[errorCode] || DEFAULT_ERROR;

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md text-center space-y-4">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
          <svg
            className="h-8 w-8 text-red-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-semibold">{info.title}</h1>

        <p className="text-gray-500">{info.description}</p>

        <Link
          href={info.action.href}
          className="inline-block rounded-md bg-violet-600 px-4 py-2 text-white font-medium hover:bg-violet-700"
        >
          {info.action.label}
        </Link>
      </div>
    </main>
  );
}

export default function AuthErrorPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center px-4">
          <p className="text-gray-500">Loading...</p>
        </main>
      }
    >
      <AuthErrorContent />
    </Suspense>
  );
}
