interface MomentumArrowProps {
  value: number;
}

export function getMomentumDirection(
  value: number,
): "rising" | "falling" | "stable" {
  if (value > 0.01) return "rising";
  if (value < -0.01) return "falling";
  return "stable";
}

export function getMomentumColor(direction: "rising" | "falling" | "stable"): string {
  switch (direction) {
    case "rising":
      return "text-green-600";
    case "falling":
      return "text-red-500";
    case "stable":
      return "text-gray-400";
  }
}

export default function MomentumArrow({ value }: MomentumArrowProps) {
  const direction = getMomentumDirection(value);
  const color = getMomentumColor(direction);

  const arrow =
    direction === "rising" ? "\u2191" : direction === "falling" ? "\u2193" : "\u2192";

  return (
    <span
      className={`text-lg font-bold ${color}`}
      data-testid="momentum-arrow"
      title={`Momentum: ${value >= 0 ? "+" : ""}${value.toFixed(2)}`}
    >
      {arrow}
    </span>
  );
}
