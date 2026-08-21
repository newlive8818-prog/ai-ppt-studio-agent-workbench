import type { NormalizedRegion } from "../types/visual-review";

const MIN_REGION_SIZE = 0.02;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function isValidNormalizedRegion(value: unknown): value is NormalizedRegion {
  if (!isRecord(value) || Object.keys(value).length !== 4) return false;
  const { x, y, width, height } = value;
  if (
    typeof x !== "number" || !Number.isFinite(x)
    || typeof y !== "number" || !Number.isFinite(y)
    || typeof width !== "number" || !Number.isFinite(width)
    || typeof height !== "number" || !Number.isFinite(height)
  ) {
    return false;
  }
  return x >= 0
    && y >= 0
    && width >= MIN_REGION_SIZE
    && height >= MIN_REGION_SIZE
    && x + width <= 1
    && y + height <= 1;
}
