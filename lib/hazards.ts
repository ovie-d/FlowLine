/**
 * Hazard groups in taxonomy order (core/taxonomy.py MODEL_TARGETS) with their
 * categorical colours. Palette: dataviz reference dark steps, validated on
 * #0B1426 and #121E36 (all checks pass; CVD worst adjacent ΔE 8.4). Colours follow
 * the hazard, never its rank — always pair them with the label (map: legend + hover).
 */
export type HazardGroup =
  | "corrosion_cracking"
  | "equipment_failure"
  | "incorrect_operation"
  | "third_party_damage"
  | "geotechnical"
  | "natural_forces_weather"
  | "construction_material_defect"
  | "fire_ignition"
  | "other_unknown"
  | "undetermined";

export const HAZARD_ORDER: HazardGroup[] = [
  "corrosion_cracking",
  "equipment_failure",
  "incorrect_operation",
  "third_party_damage",
  "geotechnical",
  "natural_forces_weather",
  "construction_material_defect",
  "fire_ignition",
];

/** Dark-theme literal colours (Mapbox paint needs literals). */
export const HAZARD_COLOR: Record<HazardGroup, string> = {
  corrosion_cracking: "#3987e5",
  equipment_failure: "#d95926",
  incorrect_operation: "#199e70",
  third_party_damage: "#c98500",
  geotechnical: "#d55181",
  natural_forces_weather: "#008300",
  construction_material_defect: "#9085e9",
  fire_ignition: "#e66767",
  other_unknown: "#6b7c9c",
  undetermined: "#6b7c9c",
};

export const HAZARD_SHORT: Record<HazardGroup, string> = {
  corrosion_cracking: "Corrosion & cracking",
  equipment_failure: "Equipment failure",
  incorrect_operation: "Incorrect operation",
  third_party_damage: "Third-party damage",
  geotechnical: "Ground movement & washout",
  natural_forces_weather: "Natural forces & weather",
  construction_material_defect: "Construction & material",
  fire_ignition: "Fire / ignition",
  other_unknown: "Other / unknown",
  undetermined: "Undetermined",
};

/** Light-theme steps of the same hues (dataviz reference light column; validated on
 * #FFFFFF / #F3F5F9 — three slots are under 3:1, so labels/legend always accompany them). */
export const HAZARD_COLOR_LIGHT: Record<HazardGroup, string> = {
  corrosion_cracking: "#2a78d6",
  equipment_failure: "#eb6834",
  incorrect_operation: "#1baf7a",
  third_party_damage: "#eda100",
  geotechnical: "#e87ba4",
  natural_forces_weather: "#008300",
  construction_material_defect: "#4a3aa7",
  fire_ignition: "#e34948",
  other_unknown: "#8a97ad",
  undetermined: "#8a97ad",
};

/** CSS colour for DOM elements: follows the active theme via --hz-* variables. */
export function hazardColor(group: string): string {
  const g = (group in HAZARD_COLOR ? group : "other_unknown") as HazardGroup;
  return `var(--hz-${g})`;
}

/** Literal colour for a theme (Mapbox paint, canvas). */
export function hazardHex(group: string, theme: "dark" | "light"): string {
  const table = theme === "light" ? HAZARD_COLOR_LIGHT : HAZARD_COLOR;
  return table[group as HazardGroup] ?? table.other_unknown;
}
