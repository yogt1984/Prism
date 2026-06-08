function getQualityLevel(score: number) {
  if (score >= 0.8) return { color: "text-green-600", label: "High" };
  if (score >= 0.5) return { color: "text-yellow-600", label: "Medium" };
  return { color: "text-red-600", label: "Low" };
}

export default function QualityIndicator({ score }: { score: number }) {
  const { color, label } = getQualityLevel(score);
  return (
    <span
      className={`text-xs font-medium ${color}`}
      data-testid="quality-indicator"
      title={`Quality: ${(score * 100).toFixed(0)}%`}
    >
      {label} quality
    </span>
  );
}

export { getQualityLevel };
