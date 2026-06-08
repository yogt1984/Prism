interface InterestToggleProps {
  category: string;
  selected: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

export default function InterestToggle({
  category,
  selected,
  onToggle,
  disabled = false,
}: InterestToggleProps) {
  const base = "px-4 py-3 rounded-lg border text-sm font-medium capitalize transition-colors";
  const styles = disabled
    ? "bg-gray-50 border-gray-100 text-gray-400 opacity-50 cursor-not-allowed"
    : selected
      ? "bg-blue-50 border-blue-500 text-blue-700"
      : "bg-white border-gray-200 text-gray-600 hover:border-gray-300";

  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className={`${base} ${styles}`}
      data-testid={`interest-toggle-${category}`}
      aria-pressed={selected}
    >
      {selected && (
        <svg
          className="inline w-4 h-4 mr-1.5 -mt-0.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          data-testid="check-icon"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 13l4 4L19 7"
          />
        </svg>
      )}
      {category}
    </button>
  );
}
