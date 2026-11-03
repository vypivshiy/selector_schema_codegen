import rawPresets from "./presets.json";

export type PresetCategory = "html" | "table" | "dict" | "raw" | "rest";

export interface PlaygroundPreset {
  id: string;
  title: string;
  category: PresetCategory;
  description: string;
  kdl: string;
  html: string;
}

export const PRESETS: readonly PlaygroundPreset[] =
  rawPresets as PlaygroundPreset[];

export const DEFAULT_PRESET: PlaygroundPreset = PRESETS[0];

/**
 * Find a curated preset by its unique ID.
 */
export function getPresetById(id: string): PlaygroundPreset | undefined {
  return PRESETS.find((preset) => preset.id === id);
}

/**
 * Detect whether the given KDL and HTML strings match one of the curated presets.
 */
export function findMatchingPresetId(
  kdl: string,
  html: string,
): string | undefined {
  const matched = PRESETS.find(
    (preset) => preset.kdl === kdl && preset.html === html,
  );
  return matched?.id;
}
