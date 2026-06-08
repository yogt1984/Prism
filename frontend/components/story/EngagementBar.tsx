"use client";

import { useRef, useState, useCallback } from "react";

interface EngagementBarProps {
  onEngage: (action: "save" | "skip", readTimeSec: number) => void;
  isPending: boolean;
  storyUrl: string;
}

export default function EngagementBar({
  onEngage,
  isPending,
  storyUrl,
}: EngagementBarProps) {
  const loadTime = useRef(Date.now());
  const [engaged, setEngaged] = useState<"save" | "skip" | null>(null);
  const [copied, setCopied] = useState(false);

  const handleAction = useCallback(
    (action: "save" | "skip") => {
      const sec = Math.floor((Date.now() - loadTime.current) / 1000);
      onEngage(action, sec);
      setEngaged(action);
    },
    [onEngage],
  );

  const handleShare = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(
        `${window.location.origin}${storyUrl}`,
      );
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard not available
    }
  }, [storyUrl]);

  const disabled = isPending || engaged !== null;

  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-gray-200 p-3"
      data-testid="engagement-bar"
    >
      <button
        onClick={() => handleAction("save")}
        disabled={disabled}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="save-btn"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
        </svg>
        {engaged === "save" ? "Saved" : "Save"}
      </button>
      <button
        onClick={() => handleAction("skip")}
        disabled={disabled}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="skip-btn"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
        {engaged === "skip" ? "Skipped" : "Skip"}
      </button>
      <button
        onClick={handleShare}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium border border-gray-300 text-gray-600 hover:bg-gray-50 ml-auto"
        data-testid="share-btn"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
        </svg>
        {copied ? "Copied!" : "Share"}
      </button>
    </div>
  );
}
