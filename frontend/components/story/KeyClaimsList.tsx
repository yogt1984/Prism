export default function KeyClaimsList({
  claimsJson,
}: {
  claimsJson: string;
}) {
  let claims: string[];
  try {
    claims = JSON.parse(claimsJson);
  } catch {
    return null;
  }

  if (!Array.isArray(claims) || claims.length === 0) return null;

  return (
    <ul className="list-disc list-inside space-y-1 text-sm text-gray-600" data-testid="key-claims">
      {claims.map((claim, i) => (
        <li key={i}>{claim}</li>
      ))}
    </ul>
  );
}
