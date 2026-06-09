import type { BriefingFormat } from "@/lib/types";
import Badge from "@/components/ui/Badge";

const FORMAT_LABELS: Record<BriefingFormat, string> = {
  email: "Email",
  json_feed: "JSON Feed",
  audio_script: "Audio",
};

export default function FormatBadge({ format }: { format: BriefingFormat }) {
  return (
    <Badge color="bg-blue-100 text-blue-700" data-testid="format-badge">
      {FORMAT_LABELS[format] ?? format}
    </Badge>
  );
}

export { FORMAT_LABELS };
