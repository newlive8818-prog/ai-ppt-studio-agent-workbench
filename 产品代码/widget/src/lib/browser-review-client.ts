import type {
  DecisionResult,
  HostBridge,
  ReviewWidgetData,
  SurfaceData,
} from "../types";

interface ReviewSessionPayload {
  ok: boolean;
  projectRoot: string;
  expectedRevision: number;
  review: ReviewWidgetData["review"];
}

interface BrowserReviewClientOptions {
  navigate?: (url: string) => void;
}

function tokenFromFragment(): string {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get("token") || "";
  if (!token) throw new Error("Review session token is missing");
  window.history.replaceState(
    null,
    document.title,
    `${window.location.pathname}${window.location.search}`,
  );
  return token;
}

async function jsonOrError(response: Response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const details = payload as { error?: { code?: string; message?: string } };
    const error = new Error(
      details.error?.message || "Browser Review request failed",
    ) as Error & { code?: string };
    error.code = details.error?.code;
    throw error;
  }
  return payload;
}

export function createBrowserReviewClient(
  options: BrowserReviewClientOptions = {},
): HostBridge & { switchReview(reviewType: "content" | "visual"): Promise<void> } {
  let token = "";
  let data: ReviewWidgetData | undefined;
  let heartbeatTimer: number | undefined;
  const navigate = options.navigate || ((url: string) => window.location.assign(url));

  async function authorizedFetch(path: string, init: RequestInit = {}) {
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token}`);
    return fetch(path, { ...init, headers: Object.fromEntries(headers.entries()) });
  }

  function startHeartbeat() {
    if (heartbeatTimer !== undefined) return;
    heartbeatTimer = window.setInterval(() => {
      void authorizedFetch("/api/heartbeat", { method: "POST" }).catch(() => {});
    }, 15_000);
  }

  return {
    async connect(onData?: (incoming: SurfaceData) => void) {
      token = tokenFromFragment();
      const response = await authorizedFetch("/api/review");
      const payload = (await jsonOrError(response)) as ReviewSessionPayload;
      data = {
        surface: "review",
        selectedProjectRoot: payload.projectRoot,
        snapshotRevision: payload.expectedRevision,
        review: payload.review,
      };
      onData?.(data);
      startHeartbeat();
    },
    async callTool<T = DecisionResult>(name: string, args: Record<string, unknown>) {
      if (name !== "save_review_marks" || !data) {
        throw new Error("Browser Review tool is unavailable");
      }
      const response = await authorizedFetch("/api/marks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expectedRevision: args.expectedRevision,
          sourceVersion: args.sourceVersion,
          marks: args.marks,
        }),
      });
      const payload = (await jsonOrError(response)) as {
        snapshotRevision: number;
      };
      data = { ...data, snapshotRevision: payload.snapshotRevision };
      return {
        snapshot: { revision: payload.snapshotRevision },
      } as T;
    },
    async switchReview(reviewType) {
      if (!data) throw new Error("Browser Review session is not connected");
      if (reviewType === data.review.review_type) return;
      const response = await authorizedFetch("/api/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewType }),
      });
      const payload = (await jsonOrError(response)) as {
        url: string;
        reviewType: "content" | "visual";
      };
      if (payload.reviewType !== reviewType) {
        throw new Error("Browser Review switch returned the wrong review type");
      }
      const target = new URL(payload.url);
      const targetToken = new URLSearchParams(target.hash.slice(1)).get("token");
      if (
        target.protocol !== "http:" ||
        target.hostname !== "127.0.0.1" ||
        target.username ||
        target.password ||
        target.pathname !== "/" ||
        target.search ||
        !targetToken
      ) {
        throw new Error("Browser Review switch returned an invalid scoped URL");
      }
      navigate(target.toString());
    },
    async updateModelContext() {
      throw new Error("Browser Review model context is unavailable");
    },
    async sendFollowUp() {
      throw new Error("Browser Review messaging is unavailable");
    },
    async confirmMission() {
      throw new Error("Browser Review mission confirmation is unavailable");
    },
    getHostEnvironment() {
      return undefined;
    },
    notifySize() {},
  };
}
