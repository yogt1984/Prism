import Badge from "@/components/ui/Badge";

export default function SentBadge({ sent }: { sent: boolean }) {
  return (
    <Badge
      color={sent ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}
      data-testid="sent-badge"
    >
      {sent ? "Sent" : "Draft"}
    </Badge>
  );
}
