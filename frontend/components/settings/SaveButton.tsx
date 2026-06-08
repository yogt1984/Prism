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
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || isPending}
      className="px-4 py-2 text-sm font-medium rounded-md bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
      data-testid="save-btn"
    >
      {isPending ? "Saving..." : label}
    </button>
  );
}
