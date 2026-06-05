export default function MomentumArrow({ momentum }: { momentum: number }) {
  if (Math.abs(momentum) < 0.1)
    return (
      <span className="text-gray-400" aria-label="flat">
        {"\u2500"}
      </span>
    );
  if (momentum > 0)
    return (
      <span className="text-green-600" aria-label="rising">
        {"\u25B2"}
      </span>
    );
  return (
    <span className="text-red-600" aria-label="falling">
      {"\u25BC"}
    </span>
  );
}
