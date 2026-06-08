const FEATURES = [
  { feature: "Topics", free: "1", pro: "All 8" },
  { feature: "Stories/briefing", free: "Up to 10", pro: "Up to 25" },
  { feature: "Formats", free: "Email", pro: "All 3" },
  { feature: "API Access", free: "\u2717", pro: "\u2713" },
  { feature: "Perception Tracking", free: "3 keywords", pro: "Unlimited" },
  { feature: "Audio Briefings", free: "\u2717", pro: "\u2713" },
];

export default function FeatureComparison() {
  return (
    <div className="overflow-x-auto" data-testid="feature-comparison">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 pr-4 font-medium text-gray-700">
              Feature
            </th>
            <th className="text-left py-2 px-4 font-medium text-gray-700">
              Free
            </th>
            <th className="text-left py-2 pl-4 font-medium text-violet-700">
              Pro ($7/mo)
            </th>
          </tr>
        </thead>
        <tbody>
          {FEATURES.map((row) => (
            <tr
              key={row.feature}
              className="border-b border-gray-100"
              data-testid="comparison-row"
            >
              <td className="py-2 pr-4 text-gray-600">{row.feature}</td>
              <td className="py-2 px-4 text-gray-500">{row.free}</td>
              <td className="py-2 pl-4 text-gray-800 font-medium">
                {row.pro}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export { FEATURES };
