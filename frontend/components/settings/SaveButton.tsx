import Button from "@/components/ui/Button";

interface SaveButtonProps {
  onClick: () => void;
  disabled: boolean;
  isPending?: boolean;
  label?: string;
}

export default function SaveButton({
  onClick,
  disabled,
  isPending = false,
  label = "Save",
}: SaveButtonProps) {
  return (
    <Button
      type="button"
      onClick={onClick}
      disabled={disabled || isPending}
      data-testid="save-btn"
    >
      {isPending ? "Saving..." : label}
    </Button>
  );
}
