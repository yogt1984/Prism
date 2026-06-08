import type { BriefingFormat } from "@/lib/types";

interface FormatOption {
  value: BriefingFormat;
  label: string;
  proOnly: boolean;
}

const FORMAT_OPTIONS: FormatOption[] = [
  { value: "email", label: "Email Newsletter", proOnly: false },
  { value: "json_feed", label: "JSON Feed (API)", proOnly: true },
  { value: "audio_script", label: "Audio Briefing", proOnly: true },
];

interface FormatSelectorProps {
  value: BriefingFormat;
  onChange: (f: BriefingFormat) => void;
  isPro: boolean;
}

export default function FormatSelector({
  value,
  onChange,
  isPro,
}: FormatSelectorProps) {
  return (
    <fieldset className="space-y-2" data-testid="format-selector">
      <legend className="text-sm font-medium text-gray-700 mb-2">
        Delivery Format
      </legend>
      {FORMAT_OPTIONS.map((opt) => {
        const locked = opt.proOnly && !isPro;
        return (
          <label
            key={opt.value}
            className={`flex items-center gap-3 px-3 py-2 rounded-md border cursor-pointer ${
              value === opt.value
                ? "border-violet-500 bg-violet-50"
                : "border-gray-200 hover:border-gray-300"
            } ${locked ? "opacity-50 cursor-not-allowed" : ""}`}
            data-testid={`format-option-${opt.value}`}
          >
            <input
              type="radio"
              name="format"
              value={opt.value}
              checked={value === opt.value}
              onChange={() => onChange(opt.value)}
              disabled={locked}
              className="accent-violet-600"
            />
            <span className="text-sm text-gray-700">{opt.label}</span>
            {locked && (
              <span
                className="ml-auto text-xs text-gray-400"
                data-testid="pro-lock"
              >
                Pro only
              </span>
            )}
          </label>
        );
      })}
    </fieldset>
  );
}

export { FORMAT_OPTIONS };
