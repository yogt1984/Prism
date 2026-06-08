interface DepthSliderProps {
  value: number;
  onChange: (n: number) => void;
  min: number;
  max: number;
}

export default function DepthSlider({
  value,
  onChange,
  min,
  max,
}: DepthSliderProps) {
  return (
    <div className="space-y-2" data-testid="depth-slider">
      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-violet-600"
        data-testid="depth-range"
      />
      <div className="flex justify-between text-xs text-gray-400">
        <span>{min}</span>
        <span
          className="text-sm font-medium text-gray-700"
          data-testid="depth-value"
        >
          {value} {value === 1 ? "story" : "stories"}
        </span>
        <span>{max}</span>
      </div>
    </div>
  );
}
