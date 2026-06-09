import type { SourceStatus } from "@/lib/types";
import Badge from "@/components/ui/Badge";

const STATUS_STYLES: Record<SourceStatus, { color: string; text: string }> = {
  seed: { color: "bg-gray-200 text-gray-700", text: "Seed" },
  candidate: { color: "bg-yellow-100 text-yellow-800", text: "Candidate" },
  probation: { color: "bg-orange-100 text-orange-800", text: "Probation" },
  trusted: { color: "bg-green-100 text-green-800", text: "Trusted" },
  rejected: { color: "bg-red-100 text-red-800", text: "Rejected" },
};

export default function StatusBadge({ status }: { status: SourceStatus }) {
  const { color, text } = STATUS_STYLES[status] ?? STATUS_STYLES.candidate;
  return (
    <Badge color={color} data-testid="status-badge">
      {text}
    </Badge>
  );
}

export { STATUS_STYLES };
