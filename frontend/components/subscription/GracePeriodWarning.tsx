"use client";

import Button from "@/components/ui/Button";

interface GracePeriodWarningProps {
  proUntil: string;
  onUpdatePayment: () => void;
  isLoading: boolean;
}

export function formatGraceDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function GracePeriodWarning({
  proUntil,
  onUpdatePayment,
  isLoading,
}: GracePeriodWarningProps) {
  return (
    <div
      className="rounded-lg border border-amber-200 bg-amber-50 p-4 flex flex-col sm:flex-row sm:items-center gap-3"
      data-testid="grace-period-warning"
    >
      <svg
        className="h-5 w-5 text-amber-500 flex-shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
        />
      </svg>
      <p className="text-sm text-amber-800 flex-1" data-testid="grace-message">
        There&apos;s an issue with your payment. Pro access continues until{" "}
        <strong>{formatGraceDate(proUntil)}</strong>.
      </p>
      <Button
        variant="danger"
        onClick={onUpdatePayment}
        disabled={isLoading}
        className="whitespace-nowrap"
        data-testid="update-payment-btn"
      >
        Update Payment Method
      </Button>
    </div>
  );
}
