import type { BiasLabel } from "@/lib/types";

const BIAS_STYLES: Record<BiasLabel, { color: string; text: string }> = {
  left: { color: "bg-blue-600 text-white", text: "Left" },
  center_left: { color: "bg-blue-300 text-blue-900", text: "Center-Left" },
  center: { color: "bg-gray-200 text-gray-800", text: "Center" },
  center_right: { color: "bg-red-300 text-red-900", text: "Center-Right" },
  right: { color: "bg-red-600 text-white", text: "Right" },
  unknown: { color: "bg-gray-100 text-gray-500", text: "Unknown" },
};

export default function BiasLabelBadge({ label }: { label: BiasLabel }) {
  const { color, text } = BIAS_STYLES[label] ?? BIAS_STYLES.unknown;
  return (
    <span
      className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${color}`}
      data-testid="bias-label"
    >
      {text}
    </span>
  );
}

export { BIAS_STYLES };
