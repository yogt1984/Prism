import type { HTMLAttributes } from "react";

type CardVariant = "default" | "large" | "alert" | "success";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant;
}

const VARIANT_CLASSES: Record<CardVariant, string> = {
  default: "rounded-lg border border-gray-200 p-4",
  large: "rounded-lg border border-gray-200 p-6",
  alert: "rounded-lg border border-violet-200 bg-violet-50 p-6",
  success: "rounded-lg border border-green-200 bg-green-50 p-4",
};

export default function Card({
  variant = "default",
  className = "",
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={`${VARIANT_CLASSES[variant]} ${className}`.trim()}
      data-testid="ui-card"
      {...props}
    >
      {children}
    </div>
  );
}

export { VARIANT_CLASSES };
export type { CardVariant, CardProps };
