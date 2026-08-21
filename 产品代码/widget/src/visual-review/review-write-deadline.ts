export const REVIEW_WRITE_DEADLINE_MS = 15_000;
export const REVIEW_WRITE_TIMEOUT_CODE = "REVIEW_WRITE_TIMEOUT";

export function isReviewWriteTimeout(error: unknown): boolean {
  return Boolean(
    error
    && typeof error === "object"
    && "code" in error
    && error.code === REVIEW_WRITE_TIMEOUT_CODE,
  );
}

function timeoutError() {
  const error = new Error("Review write request timed out") as Error & { code: string };
  error.code = REVIEW_WRITE_TIMEOUT_CODE;
  return error;
}

export function withReviewWriteDeadline<T>(
  operation: (signal: AbortSignal) => Promise<T>,
): Promise<T> {
  const controller = new AbortController();

  return new Promise<T>((resolve, reject) => {
    let settled = false;
    const timer = globalThis.setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(timeoutError());
      controller.abort();
    }, REVIEW_WRITE_DEADLINE_MS);

    let pending: Promise<T>;
    try {
      pending = operation(controller.signal);
    } catch (error) {
      settled = true;
      globalThis.clearTimeout(timer);
      reject(error);
      return;
    }

    pending.then(
      (value) => {
        if (settled) return;
        settled = true;
        globalThis.clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        if (settled) return;
        settled = true;
        globalThis.clearTimeout(timer);
        reject(error);
      },
    );
  });
}
