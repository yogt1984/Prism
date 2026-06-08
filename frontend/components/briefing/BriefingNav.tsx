import Link from "next/link";

interface BriefingNavProps {
  prevId: number | null;
  nextId: number | null;
}

export default function BriefingNav({ prevId, nextId }: BriefingNavProps) {
  if (!prevId && !nextId) return null;

  return (
    <nav
      className="flex items-center justify-between border-t border-gray-200 pt-4"
      data-testid="briefing-nav"
    >
      {prevId ? (
        <Link
          href={`/briefings/${prevId}`}
          className="inline-flex items-center gap-1 text-sm text-gray-600 hover:text-violet-600"
          data-testid="nav-prev"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Previous briefing
        </Link>
      ) : (
        <span />
      )}
      {nextId ? (
        <Link
          href={`/briefings/${nextId}`}
          className="inline-flex items-center gap-1 text-sm text-gray-600 hover:text-violet-600"
          data-testid="nav-next"
        >
          Next briefing
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
