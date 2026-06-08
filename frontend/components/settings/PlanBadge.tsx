export default function PlanBadge({ tier }: { tier: "Free" | "Pro" }) {
  const styles =
    tier === "Pro"
      ? "bg-violet-100 text-violet-700"
      : "bg-gray-100 text-gray-600";

  return (
    <span
      className={`inline-flex items-center px-3 py-1 text-sm font-medium rounded-full ${styles}`}
      data-testid="plan-badge"
    >
      {tier}
    </span>
  );
}
