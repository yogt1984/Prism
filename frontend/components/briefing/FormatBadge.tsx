import type { BriefingFormat } from "@/lib/types";

const FORMAT_LABELS: Record<BriefingFormat, string> = {
  email: "Email",
  json_feed: "JSON Feed",
  audio_script: "Audio",
};

export default function FormatBadge({ format }: { format: BriefingFormat }) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-700"
      data-testid="format-badge"
    >
      {FORMAT_LABELS[format] ?? format}
    </span>
  );
}

export { FORMAT_LABELS };
