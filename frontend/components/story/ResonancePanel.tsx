import MomentumArrow from "@/components/dashboard/MomentumArrow";
import type { Resonance } from "@/lib/types";

interface ResonancePanelProps {
  resonance?: Resonance | null;
  isLoading: boolean;
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <p className="text-lg font-semibold">{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}

export default function ResonancePanel({
  resonance,
  isLoading,
}: ResonancePanelProps) {
  if (isLoading) {
    return (
      <div
        className="rounded-lg border border-gray-200 p-4 grid grid-cols-2 lg:grid-cols-5 gap-4"
        data-testid="resonance-skeleton"
      >
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded bg-gray-100" />
        ))}
      </div>
    );
  }

  if (!resonance) {
    return (
      <div
        className="rounded-lg border border-gray-200 p-4 grid grid-cols-2 lg:grid-cols-5 gap-4"
        data-testid="resonance-empty"
      >
        <Stat value="\u2014" label="resonance" />
        <Stat value="\u2014" label="momentum" />
        <Stat value="\u2014" label="peak" />
        <Stat value="\u2014" label="sources" />
        <Stat value="\u2014" label="breadth" />
      </div>
    );
  }

  return (
    <div
      className="rounded-lg border border-gray-200 p-4 grid grid-cols-2 lg:grid-cols-5 gap-4"
      data-testid="resonance-panel"
    >
      <Stat value={resonance.resonance.toFixed(2)} label="resonance" />
      <div className="text-center">
        <p className="text-lg font-semibold inline-flex items-center gap-1">
          <MomentumArrow momentum={resonance.momentum} />
          {resonance.momentum.toFixed(2)}
        </p>
        <p className="text-xs text-gray-500">momentum</p>
      </div>
      <Stat value={resonance.peak_resonance.toFixed(2)} label="peak" />
      <Stat value={String(resonance.source_count)} label="sources" />
      <Stat value={resonance.breadth.toFixed(2)} label="breadth" />
    </div>
  );
}
