function getMarkerColor(sentiment: number): string {
  if (sentiment < -0.3) return "bg-red-500";
  if (sentiment < -0.1) return "bg-orange-400";
  if (sentiment <= 0.1) return "bg-gray-400";
  if (sentiment <= 0.3) return "bg-lime-400";
  return "bg-green-500";
}

export default function SentimentBar({ value }: { value: number }) {
  const pct = ((value + 1) / 2) * 100;

  return (
    <div
      className="w-full h-2 bg-gray-100 rounded-full relative"
      data-testid="sentiment-bar"
      aria-label={`Sentiment: ${value.toFixed(2)}`}
    >
      <div className="absolute top-1/2 left-1/2 w-px h-full -translate-x-1/2 -translate-y-1/2 bg-gray-300" />
      <div
        className={`absolute w-3 h-3 rounded-full -translate-x-1/2 -translate-y-[2px] ${getMarkerColor(value)}`}
        style={{ left: `${pct}%` }}
        data-testid="sentiment-marker"
      />
    </div>
  );
}

export { getMarkerColor };
