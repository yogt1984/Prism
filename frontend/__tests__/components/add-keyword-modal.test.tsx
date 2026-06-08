import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AddKeywordModal from "@/components/perception/AddKeywordModal";

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  onSubmit: vi.fn(),
  isPending: false,
  error: null,
};

describe("AddKeywordModal", () => {
  it("renders nothing when closed", () => {
    render(<AddKeywordModal {...defaultProps} open={false} />);
    expect(screen.queryByTestId("add-keyword-modal")).toBeNull();
  });

  it("renders modal when open", () => {
    render(<AddKeywordModal {...defaultProps} />);
    expect(screen.getByTestId("add-keyword-modal")).toBeInTheDocument();
    expect(screen.getByText("Track a New Keyword")).toBeInTheDocument();
  });

  it("renders keyword input", () => {
    render(<AddKeywordModal {...defaultProps} />);
    expect(screen.getByTestId("keyword-input")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("e.g., tariffs")).toBeInTheDocument();
  });

  it("renders aliases input", () => {
    render(<AddKeywordModal {...defaultProps} />);
    expect(screen.getByTestId("aliases-input")).toBeInTheDocument();
  });

  it("renders category select with all categories", () => {
    render(<AddKeywordModal {...defaultProps} />);
    const select = screen.getByTestId("category-select");
    expect(select).toBeInTheDocument();
    const options = select.querySelectorAll("option");
    // 8 categories + "None" = 9
    expect(options).toHaveLength(9);
  });

  it("submits with correct payload", () => {
    const onSubmit = vi.fn();
    render(<AddKeywordModal {...defaultProps} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("keyword-input"), {
      target: { value: "tariffs" },
    });
    fireEvent.change(screen.getByTestId("aliases-input"), {
      target: { value: "trade war, import duties" },
    });
    fireEvent.change(screen.getByTestId("category-select"), {
      target: { value: "finance" },
    });
    fireEvent.click(screen.getByTestId("modal-submit-btn"));

    expect(onSubmit).toHaveBeenCalledWith({
      keyword: "tariffs",
      aliases: "trade war, import duties",
      category: "finance",
    });
  });

  it("validates empty keyword", () => {
    const onSubmit = vi.fn();
    render(<AddKeywordModal {...defaultProps} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByTestId("modal-submit-btn"));
    expect(screen.getByTestId("modal-error")).toHaveTextContent(
      "Keyword is required",
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("validates whitespace-only keyword", () => {
    const onSubmit = vi.fn();
    render(<AddKeywordModal {...defaultProps} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByTestId("keyword-input"), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByTestId("modal-submit-btn"));
    expect(screen.getByTestId("modal-error")).toHaveTextContent(
      "Keyword is required",
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("validates keyword with commas", () => {
    const onSubmit = vi.fn();
    render(<AddKeywordModal {...defaultProps} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByTestId("keyword-input"), {
      target: { value: "tariffs, trade" },
    });
    fireEvent.click(screen.getByTestId("modal-submit-btn"));
    expect(screen.getByTestId("modal-error")).toHaveTextContent(
      "Keyword cannot contain commas",
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("validates keyword over 100 characters", () => {
    const onSubmit = vi.fn();
    render(<AddKeywordModal {...defaultProps} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByTestId("keyword-input"), {
      target: { value: "a".repeat(101) },
    });
    fireEvent.click(screen.getByTestId("modal-submit-btn"));
    expect(screen.getByTestId("modal-error")).toHaveTextContent(
      "Keyword must be 100 characters or fewer",
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("trims keyword before submitting", () => {
    const onSubmit = vi.fn();
    render(<AddKeywordModal {...defaultProps} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByTestId("keyword-input"), {
      target: { value: "  tariffs  " },
    });
    fireEvent.click(screen.getByTestId("modal-submit-btn"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ keyword: "tariffs" }),
    );
  });

  it("shows server error", () => {
    render(
      <AddKeywordModal
        {...defaultProps}
        error="Already tracking this keyword"
      />,
    );
    expect(screen.getByTestId("modal-error")).toHaveTextContent(
      "Already tracking this keyword",
    );
  });

  it("disables submit button when pending", () => {
    render(<AddKeywordModal {...defaultProps} isPending={true} />);
    const btn = screen.getByTestId("modal-submit-btn");
    expect(btn).toBeDisabled();
    expect(btn).toHaveTextContent("Adding...");
  });

  it("shows Start Tracking when not pending", () => {
    render(<AddKeywordModal {...defaultProps} />);
    expect(screen.getByTestId("modal-submit-btn")).toHaveTextContent(
      "Start Tracking",
    );
  });

  it("calls onClose when close button clicked", () => {
    const onClose = vi.fn();
    render(<AddKeywordModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByTestId("modal-close-btn"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when cancel button clicked", () => {
    const onClose = vi.fn();
    render(<AddKeywordModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByTestId("modal-cancel-btn"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("clears validation error on re-submit with valid input", () => {
    const onSubmit = vi.fn();
    render(<AddKeywordModal {...defaultProps} onSubmit={onSubmit} />);

    // Trigger validation error
    fireEvent.click(screen.getByTestId("modal-submit-btn"));
    expect(screen.getByTestId("modal-error")).toBeInTheDocument();

    // Fix and re-submit
    fireEvent.change(screen.getByTestId("keyword-input"), {
      target: { value: "tariffs" },
    });
    fireEvent.click(screen.getByTestId("modal-submit-btn"));
    expect(screen.queryByTestId("modal-error")).toBeNull();
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("submits with empty aliases and category", () => {
    const onSubmit = vi.fn();
    render(<AddKeywordModal {...defaultProps} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByTestId("keyword-input"), {
      target: { value: "tariffs" },
    });
    fireEvent.click(screen.getByTestId("modal-submit-btn"));
    expect(onSubmit).toHaveBeenCalledWith({
      keyword: "tariffs",
      aliases: "",
      category: "",
    });
  });

  it("has maxLength 100 on keyword input", () => {
    render(<AddKeywordModal {...defaultProps} />);
    expect(screen.getByTestId("keyword-input")).toHaveAttribute(
      "maxLength",
      "100",
    );
  });
});
