import MomentumArrow, { getMomentumDirection } from "./MomentumArrow";

interface MomentumIndicatorProps {
  momentum: number;
}

export default function MomentumIndicator({
  momentum,
}: MomentumIndicatorProps) {
  const direction = getMomentumDirection(momentum);
  const trendText =
    direction === "rising"
      ? "Rising"
      : direction === "falling"
        ? "Falling"
        : "Stable";
  const sign = momentum >= 0 ? "+" : "";

  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-gray-200 p-4"
      data-testid="momentum-indicator"
    >
      <MomentumArrow value={momentum} />
      <div>
        <p className="text-sm font-medium text-gray-900" data-testid="trend-label">
          {trendText}
        </p>
        <p className="text-xs text-gray-500" data-testid="trend-explanation">
          Perception shifted {sign}
          {momentum.toFixed(2)} in last scan
        </p>
      </div>
    </div>
  );
}
