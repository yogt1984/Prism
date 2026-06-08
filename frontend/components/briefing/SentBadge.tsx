export default function SentBadge({ sent }: { sent: boolean }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${
        sent
          ? "bg-green-100 text-green-700"
          : "bg-yellow-100 text-yellow-700"
      }`}
      data-testid="sent-badge"
    >
      {sent ? "Sent" : "Draft"}
    </span>
  );
}
