import BiasLabelBadge from "./BiasLabelBadge";
import SentimentBar from "./SentimentBar";
import KeyClaimsList from "./KeyClaimsList";
import type { Perspective, Source } from "@/lib/types";

interface PerspectiveCardProps {
  perspective: Perspective;
  source?: Source;
}

export default function PerspectiveCard({
  perspective,
  source,
}: PerspectiveCardProps) {
  return (
    <div
      className="rounded-lg border border-gray-200 p-4 space-y-3"
      data-testid="perspective-card"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-sm truncate">
          {source?.name ?? `Source #${perspective.source_id}`}
        </span>
        <BiasLabelBadge label={perspective.bias_label} />
      </div>
      <SentimentBar value={perspective.sentiment} />
      <p className="text-sm text-gray-700">{perspective.summary}</p>
      <KeyClaimsList claimsJson={perspective.key_claims} />
    </div>
  );
}
