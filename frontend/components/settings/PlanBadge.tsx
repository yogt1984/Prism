import Badge from "@/components/ui/Badge";

export default function PlanBadge({ tier }: { tier: "Free" | "Pro" }) {
  const color =
    tier === "Pro"
      ? "bg-violet-100 text-violet-700"
      : "bg-gray-100 text-gray-600";

  return (
    <Badge color={color} size="md" data-testid="plan-badge">
      {tier}
    </Badge>
  );
}
