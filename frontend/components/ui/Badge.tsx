import type { HTMLAttributes, ReactNode } from "react";

type BadgeSize = "sm" | "md";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  color?: string;
  size?: BadgeSize;
  children: ReactNode;
}

const SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-3 py-1 text-sm",
};

export default function Badge({
  color = "bg-gray-100 text-gray-600",
  size = "sm",
  className = "",
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center font-medium rounded-full ${SIZE_CLASSES[size]} ${color} ${className}`.trim()}
      data-testid="ui-badge"
      {...props}
    >
      {children}
    </span>
  );
}

export { SIZE_CLASSES };
export type { BadgeSize, BadgeProps };
