export interface NormalizedQuantity {
  valueSI: number;
  dimension: string;
  canonicalUnit: string;
  displayUnit: string;
}

interface UnitDefinition {
  dimension: string;
  canonicalUnit: string;
  scale: number;
  offset?: number;
}

const UNIT_DEFINITIONS: Readonly<Record<string, UnitDefinition>> = Object.freeze({
  m: { dimension: "length", canonicalUnit: "m", scale: 1 },
  cm: { dimension: "length", canonicalUnit: "m", scale: 0.01 },
  mm: { dimension: "length", canonicalUnit: "m", scale: 0.001 },
  in: { dimension: "length", canonicalUnit: "m", scale: 0.0254 },
});

export function normalizeQuantity(value: number, unit: string): Readonly<NormalizedQuantity> {
  if (!Number.isFinite(value)) throw new TypeError("quantity value must be finite");
  const definition = UNIT_DEFINITIONS[unit];
  if (!definition) throw new RangeError(`unsupported unit: ${unit}`);
  const valueSI = (value + (definition.offset ?? 0)) * definition.scale;
  return Object.freeze({
    valueSI: Object.is(valueSI, -0) ? 0 : valueSI,
    dimension: definition.dimension,
    canonicalUnit: definition.canonicalUnit,
    displayUnit: unit,
  });
}
