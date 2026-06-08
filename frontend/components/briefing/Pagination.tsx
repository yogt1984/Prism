interface PaginationProps {
  offset: number;
  pageSize: number;
  itemCount: number;
  onPrevious: () => void;
  onNext: () => void;
}

export default function Pagination({
  offset,
  pageSize,
  itemCount,
  onPrevious,
  onNext,
}: PaginationProps) {
  const page = Math.floor(offset / pageSize) + 1;
  const hasPrevious = offset > 0;
  const hasNext = itemCount >= pageSize;

  return (
    <div
      className="flex items-center justify-between border-t border-gray-200 pt-4"
      data-testid="pagination"
    >
      <button
        onClick={onPrevious}
        disabled={!hasPrevious}
        className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="pagination-prev"
      >
        Previous
      </button>
      <span className="text-sm text-gray-500" data-testid="pagination-info">
        Page {page}
      </span>
      <button
        onClick={onNext}
        disabled={!hasNext}
        className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="pagination-next"
      >
        Next
      </button>
    </div>
  );
}
