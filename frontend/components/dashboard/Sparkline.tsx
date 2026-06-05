interface SparklineProps {
  data: { perception: number; computed_at: string }[];
  width?: number;
  height?: number;
  momentum?: number;
}

export default function Sparkline({
  data,
  width = 80,
  height = 24,
  momentum = 0,
}: SparklineProps) {
  if (data.length === 0) return null;

  const min = -1;
  const max = 1;
  const range = max - min;

  const points = data
    .map((d, i) => {
      const x =
        data.length === 1 ? width / 2 : (i / (data.length - 1)) * width;
      const y = height - ((d.perception - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const color =
    momentum > 0.1 ? "#22c55e" : momentum < -0.1 ? "#ef4444" : "#9ca3af";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Perception sparkline"
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
      />
    </svg>
  );
}
