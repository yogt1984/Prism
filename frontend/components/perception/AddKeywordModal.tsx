"use client";

import { useState } from "react";
import { CATEGORIES } from "@/lib/types";

interface AddKeywordModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    keyword: string;
    aliases: string;
    category: string;
  }) => void;
  isPending: boolean;
  error: string | null;
}

export default function AddKeywordModal({
  open,
  onClose,
  onSubmit,
  isPending,
  error,
}: AddKeywordModalProps) {
  const [keyword, setKeyword] = useState("");
  const [aliases, setAliases] = useState("");
  const [category, setCategory] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  if (!open) return null;

  function handleSubmit() {
    setValidationError(null);

    const trimmed = keyword.trim();
    if (!trimmed) {
      setValidationError("Keyword is required");
      return;
    }
    if (trimmed.includes(",")) {
      setValidationError("Keyword cannot contain commas");
      return;
    }
    if (trimmed.length > 100) {
      setValidationError("Keyword must be 100 characters or fewer");
      return;
    }

    onSubmit({ keyword: trimmed, aliases: aliases.trim(), category });
  }

  function handleClose() {
    setKeyword("");
    setAliases("");
    setCategory("");
    setValidationError(null);
    onClose();
  }

  const displayError = validationError || error;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      data-testid="add-keyword-modal"
    >
      <div className="bg-white rounded-lg shadow-lg w-full max-w-md p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900">
            Track a New Keyword
          </h2>
          <button
            type="button"
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600"
            data-testid="modal-close-btn"
          >
            &times;
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Keyword *
            </label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="e.g., tariffs"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-violet-500"
              data-testid="keyword-input"
              maxLength={100}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Aliases
            </label>
            <input
              type="text"
              value={aliases}
              onChange={(e) => setAliases(e.target.value)}
              placeholder="e.g., trade war, import duties"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-violet-500"
              data-testid="aliases-input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-violet-500"
              data-testid="category-select"
            >
              <option value="">None</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {displayError && (
          <p
            className="text-sm text-red-600"
            data-testid="modal-error"
          >
            {displayError}
          </p>
        )}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
            data-testid="modal-cancel-btn"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isPending}
            className="px-4 py-2 text-sm font-medium rounded-md bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="modal-submit-btn"
          >
            {isPending ? "Adding..." : "Start Tracking"}
          </button>
        </div>
      </div>
    </div>
  );
}
