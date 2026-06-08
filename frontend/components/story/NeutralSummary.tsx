export default function NeutralSummary({ text }: { text: string }) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        Neutral Summary
      </h2>
      <p className="text-gray-700 leading-relaxed">{text}</p>
    </section>
  );
}
