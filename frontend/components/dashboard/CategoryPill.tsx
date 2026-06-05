const CATEGORY_COLORS: Record<string, string> = {
  finance: "bg-emerald-100 text-emerald-700",
  politics: "bg-red-100 text-red-700",
  technology: "bg-blue-100 text-blue-700",
  sports: "bg-orange-100 text-orange-700",
  culture: "bg-purple-100 text-purple-700",
  science: "bg-cyan-100 text-cyan-700",
  health: "bg-pink-100 text-pink-700",
  world: "bg-amber-100 text-amber-700",
};

export default function CategoryPill({ category }: { category: string }) {
  const color = CATEGORY_COLORS[category] ?? "bg-gray-100 text-gray-600";
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${color}`}
    >
      {category}
    </span>
  );
}

export { CATEGORY_COLORS };
