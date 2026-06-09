import Button from "@/components/ui/Button";

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
      <Button
        variant="secondary"
        size="sm"
        onClick={onPrevious}
        disabled={!hasPrevious}
        data-testid="pagination-prev"
      >
        Previous
      </Button>
      <span className="text-sm text-gray-500" data-testid="pagination-info">
        Page {page}
      </span>
      <Button
        variant="secondary"
        size="sm"
        onClick={onNext}
        disabled={!hasNext}
        data-testid="pagination-next"
      >
        Next
      </Button>
    </div>
  );
}
