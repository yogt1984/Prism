export default function PlainTextRenderer({ text }: { text: string }) {
  return (
    <pre
      className="whitespace-pre-wrap text-sm text-gray-700 leading-relaxed font-sans"
      data-testid="plaintext-renderer"
    >
      {text}
    </pre>
  );
}
