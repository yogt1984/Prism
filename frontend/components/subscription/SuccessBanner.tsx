"use client";

import { useEffect, useState } from "react";

interface SuccessBannerProps {
  onDismiss: () => void;
  autoHideMs?: number;
}

export default function SuccessBanner({
  onDismiss,
  autoHideMs = 8000,
}: SuccessBannerProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onDismiss();
    }, autoHideMs);
    return () => clearTimeout(timer);
  }, [autoHideMs, onDismiss]);

  if (!visible) return null;

  return (
    <div
      className="rounded-lg border border-green-200 bg-green-50 p-4 flex items-center gap-3"
      data-testid="success-banner"
    >
      <svg
        className="h-5 w-5 text-green-500 flex-shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <div className="flex-1">
        <p className="text-sm font-semibold text-green-800">
          Welcome to Prism Pro!
        </p>
        <p className="text-sm text-green-700">
          All Pro features are now active.
        </p>
      </div>
      <button
        onClick={() => {
          setVisible(false);
          onDismiss();
        }}
        className="text-green-600 hover:text-green-800 text-sm"
        data-testid="dismiss-banner"
      >
        Dismiss
      </button>
    </div>
  );
}
