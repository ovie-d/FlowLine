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

export function hazardColor(group: string): string {
  return HAZARD_COLOR[group as HazardGroup] ?? HAZARD_COLOR.other_unknown;
}
