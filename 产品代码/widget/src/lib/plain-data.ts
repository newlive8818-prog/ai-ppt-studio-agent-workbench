export const PLAIN_DATA_MAX_DEPTH = 64;
export const PLAIN_DATA_MAX_NODES = 20_000;
export const PLAIN_DATA_MAX_ARRAY_LENGTH = 4_096;

type PlainRecord = Record<string, unknown>;

interface CloneState {
  nodes: number;
  seen: WeakSet<object>;
}

function cloneValue(value: unknown, depth: number, state: CloneState): unknown | undefined {
  state.nodes += 1;
  if (state.nodes > PLAIN_DATA_MAX_NODES || depth > PLAIN_DATA_MAX_DEPTH) return undefined;
  if (value === null || typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number") return Number.isFinite(value) ? value : undefined;
  if (typeof value !== "object") return undefined;
  if (state.seen.has(value)) return undefined;
  state.seen.add(value);

  if (Array.isArray(value)) {
    if (Object.getPrototypeOf(value) !== Array.prototype) return undefined;
    const lengthDescriptor = Object.getOwnPropertyDescriptor(value, "length");
    if (!lengthDescriptor || !("value" in lengthDescriptor) || lengthDescriptor.enumerable) return undefined;
    const length = lengthDescriptor.value;
    if (!Number.isSafeInteger(length) || length < 0 || length > PLAIN_DATA_MAX_ARRAY_LENGTH) return undefined;
    const keys = Reflect.ownKeys(value);
    if (keys.length !== length + 1) return undefined;
    const copy: unknown[] = [];
    for (let index = 0; index < length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      if (!descriptor || !("value" in descriptor) || !descriptor.enumerable) return undefined;
      const item = cloneValue(descriptor.value, depth + 1, state);
      if (item === undefined) return undefined;
      copy.push(item);
    }
    return copy;
  }

  if (Object.getPrototypeOf(value) !== Object.prototype) return undefined;
  const copy: PlainRecord = {};
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string") return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor || !("value" in descriptor) || !descriptor.enumerable) return undefined;
    const item = cloneValue(descriptor.value, depth + 1, state);
    if (item === undefined) return undefined;
    Object.defineProperty(copy, key, {
      configurable: true,
      enumerable: true,
      value: item,
      writable: true,
    });
  }
  return copy;
}

export function clonePlainData(value: unknown): unknown | undefined {
  try {
    return cloneValue(value, 0, { nodes: 0, seen: new WeakSet<object>() });
  } catch {
    return undefined;
  }
}
