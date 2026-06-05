interface ResonanceBadgeProps {
  score: number;
  momentum?: number;
}

function getResonanceLevel(score: number) {
  if (score >= 5)
    return { color: "bg-red-100 text-red-700", label: "Viral" };
  if (score >= 3)
    return { color: "bg-orange-100 text-orange-700", label: "High" };
  if (score >= 1)
    return { color: "bg-blue-100 text-blue-700", label: "Moderate" };
  return { color: "bg-gray-100 text-gray-600", label: "Low" };
}

function getMomentumArrow(momentum?: number) {
  if (momentum == null || Math.abs(momentum) < 0.1) return "\u2500";
  return momentum > 0 ? "\u25B2" : "\u25BC";
}

export default function ResonanceBadge({
  score,
  momentum,
}: ResonanceBadgeProps) {
  const { color, label } = getResonanceLevel(score);
  const arrow = getMomentumArrow(momentum);

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${color}`}
      data-testid="resonance-badge"
    >
      {score.toFixed(1)} {label} {arrow}
    </span>
  );
}

export { getResonanceLevel, getMomentumArrow };
