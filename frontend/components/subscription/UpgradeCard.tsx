"use client";

const FEATURES = [
  "All 8 topic categories",
  "Up to 25 stories per briefing",
  "Audio briefings",
  "JSON API access",
  "Unlimited keyword tracking",
];

interface UpgradeCardProps {
  onUpgrade: () => void;
  isLoading: boolean;
}

export default function UpgradeCard({ onUpgrade, isLoading }: UpgradeCardProps) {
  return (
    <div
      className="rounded-lg border border-violet-200 bg-violet-50 p-6"
      data-testid="upgrade-card"
    >
      <h3 className="text-lg font-semibold mb-1">Upgrade to Pro</h3>
      <p className="text-2xl font-bold mb-4">
        $7<span className="text-sm font-normal text-gray-500">/month</span>
      </p>
      <ul className="space-y-2 mb-6" data-testid="feature-list">
        {FEATURES.map((f) => (
          <li key={f} className="flex items-center gap-2 text-sm text-gray-700">
            <svg
              className="h-4 w-4 text-violet-500 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            {f}
          </li>
        ))}
      </ul>
      <button
        onClick={onUpgrade}
        disabled={isLoading}
        className="w-full px-4 py-2 text-sm font-medium rounded-md bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="upgrade-btn"
      >
        {isLoading ? "Redirecting to payment..." : "Upgrade Now"}
      </button>
    </div>
  );
}

export { FEATURES };
