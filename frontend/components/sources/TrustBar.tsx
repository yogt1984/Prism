interface TrustBarProps {
  value: number; // 0.0 to 1.0
}

export function getTrustColor(value: number): string {
  if (value < 0.3) return "bg-red-400";
  if (value < 0.6) return "bg-yellow-400";
  if (value < 0.8) return "bg-green-400";
  return "bg-green-600";
}

export function getTrustLabel(value: number): string {
  if (value < 0.3) return "Low";
  if (value < 0.6) return "Medium";
  if (value < 0.8) return "Good";
  return "High";
}

export default function TrustBar({ value }: TrustBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const color = getTrustColor(clamped);
  const label = getTrustLabel(clamped);

  return (
    <div className="flex items-center gap-2" data-testid="trust-bar">
      <div
        className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden"
        role="progressbar"
        aria-valuenow={Math.round(clamped * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Trust: ${label}`}
      >
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${clamped * 100}%` }}
          data-testid="trust-bar-fill"
        />
      </div>
      <span className="text-sm text-gray-600 tabular-nums" data-testid="trust-value">
        {clamped.toFixed(2)}
      </span>
    </div>
  );
}
