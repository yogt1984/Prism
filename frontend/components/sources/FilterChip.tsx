interface FilterChipProps {
  label: string;
  active: boolean;
  onClick: () => void;
  color?: string; // tailwind bg class for the dot indicator
}

export default function FilterChip({
  label,
  active,
  onClick,
  color,
}: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3 py-1 text-sm font-medium rounded-full border transition-colors ${
        active
          ? "bg-gray-800 text-white border-gray-800"
          : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
      }`}
      data-testid={`filter-chip-${label.toLowerCase().replace(/\s+/g, "-")}`}
      aria-pressed={active}
    >
      {color && (
        <span
          className={`inline-block w-2 h-2 rounded-full ${color}`}
          data-testid="chip-dot"
        />
      )}
      {label}
    </button>
  );
}
