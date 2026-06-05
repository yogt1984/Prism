import { describe, it, expect } from "vitest";
import { CATEGORIES } from "@/lib/types";
import type { Category, BiasLabel, BriefingFormat } from "@/lib/types";

describe("CATEGORIES constant", () => {
  it("contains all 8 categories", () => {
    expect(CATEGORIES).toHaveLength(8);
  });

  it("includes expected values", () => {
    const expected: Category[] = [
      "finance",
      "politics",
      "technology",
      "sports",
      "culture",
      "science",
      "health",
      "world",
    ];
    expect(CATEGORIES).toEqual(expected);
  });

  it("categories are all lowercase strings", () => {
    for (const cat of CATEGORIES) {
      expect(cat).toBe(cat.toLowerCase());
      expect(typeof cat).toBe("string");
    }
  });
});

describe("type exports", () => {
  it("BiasLabel type allows valid values", () => {
    const label: BiasLabel = "center_left";
    expect(label).toBe("center_left");
  });

  it("BriefingFormat type allows valid values", () => {
    const format: BriefingFormat = "audio_script";
    expect(format).toBe("audio_script");
  });
});
