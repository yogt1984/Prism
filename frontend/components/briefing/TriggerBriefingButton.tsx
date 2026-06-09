"use client";

import { useState, useCallback, useEffect } from "react";
import Button from "@/components/ui/Button";

const RATE_GUARD_MS = 60_000;
const STORAGE_KEY = "prism:last-briefing-trigger";

interface TriggerBriefingButtonProps {
  onTrigger: () => void;
  isPending: boolean;
}

export default function TriggerBriefingButton({
  onTrigger,
  isPending,
}: TriggerBriefingButtonProps) {
  const [cooldown, setCooldown] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const elapsed = Date.now() - Number(stored);
      if (elapsed < RATE_GUARD_MS) {
        setCooldown(true);
        const timer = setTimeout(
          () => setCooldown(false),
          RATE_GUARD_MS - elapsed,
        );
        return () => clearTimeout(timer);
      }
    }
  }, []);

  const handleClick = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, String(Date.now()));
    setCooldown(true);
    setTimeout(() => setCooldown(false), RATE_GUARD_MS);
    onTrigger();
  }, [onTrigger]);

  const disabled = isPending || cooldown;

  return (
    <Button
      onClick={handleClick}
      disabled={disabled}
      className="inline-flex items-center gap-2"
      data-testid="trigger-briefing-btn"
    >
      {isPending && (
        <svg
          className="animate-spin w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          data-testid="trigger-spinner"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      {isPending ? "Generating..." : "Generate new briefing"}
    </Button>
  );
}

export { RATE_GUARD_MS, STORAGE_KEY };
