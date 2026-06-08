export default function PromptVersionTag({ version }: { version: string }) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-500"
      data-testid="prompt-version-tag"
    >
      {version}
    </span>
  );
}
