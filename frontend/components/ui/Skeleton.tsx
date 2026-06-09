interface SkeletonProps {
  className?: string;
  height?: string;
  rounded?: "sm" | "md" | "lg" | "full";
}

const ROUNDED_CLASSES = {
  sm: "rounded",
  md: "rounded-md",
  lg: "rounded-lg",
  full: "rounded-full",
};

export default function Skeleton({
  className = "",
  height = "h-4",
  rounded = "md",
}: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-gray-100 ${ROUNDED_CLASSES[rounded]} ${height} ${className}`.trim()}
      data-testid="ui-skeleton"
    />
  );
}

export { ROUNDED_CLASSES };
export type { SkeletonProps };
