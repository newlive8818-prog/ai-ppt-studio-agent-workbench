import { afterEach, describe, expect, it, vi } from "vitest";

import { createBrowserReviewClient } from "./lib/browser-review-client";

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("Browser Review loopback client", () => {
  it("removes the fragment token and reads the scoped review with Bearer", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          ok: true,
          projectRoot: "/managed/project",
          expectedRevision: 7,
          review: {
            review_type: "content",
            project_id: "p1",
            project_name: "测试项目",
            source_version: "content-v1",
            sections: [],
            outline: [],
            mark_set: { marks: [] },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = createBrowserReviewClient();
    const received = vi.fn();

    await client.connect(received);

    expect(window.location.hash).toBe("");
    expect(fetchMock).toHaveBeenCalledWith("/api/review", {
      headers: { authorization: "Bearer short-lived-token" },
    });
    expect(received).toHaveBeenCalledWith(
      expect.objectContaining({
        surface: "review",
        selectedProjectRoot: "/managed/project",
        snapshotRevision: 7,
      }),
    );
  });

  it("saves marks through the scoped Browser API", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            projectRoot: "/managed/project",
            expectedRevision: 7,
            review: {
              review_type: "content",
              project_id: "p1",
              project_name: "测试项目",
              source_version: "content-v1",
              sections: [],
              outline: [],
              mark_set: { marks: [] },
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true, snapshotRevision: 8 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const client = createBrowserReviewClient();
    await client.connect();

    const result = await client.callTool(
      "save_review_marks",
      {
        expectedRevision: 7,
        sourceVersion: "content-v1",
        marks: [],
      },
    );

    expect(result.snapshot.revision).toBe(8);
  });

  it("surfaces a stable save-capability error when the scoped Bridge session expired", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            projectRoot: "/managed/project",
            expectedRevision: 7,
            review: {
              review_type: "content",
              project_id: "p1",
              project_name: "测试项目",
              source_version: "content-v1",
              sections: [],
              outline: [],
              mark_set: { marks: [] },
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: false,
            error: { code: "REVIEW_SESSION_EXPIRED", message: "Review session expired." },
          }),
          { status: 410, headers: { "Content-Type": "application/json" } },
        ),
      );
    const client = createBrowserReviewClient();
    await client.connect();

    await expect(client.callTool("save_review_marks", {
      expectedRevision: 7,
      sourceVersion: "content-v1",
      marks: [],
    })).rejects.toMatchObject({ code: "BROWSER_REVIEW_SAVE_UNAVAILABLE" });
  });

  it("switches through the authenticated Bridge endpoint and navigates to the new scoped session", async () => {
    window.history.replaceState(null, "", "/#token=short-lived-token");
    const navigate = vi.fn();
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            projectRoot: "/managed/project",
            expectedRevision: 7,
            review: {
              review_type: "content",
              project_id: "p1",
              project_name: "测试项目",
              source_version: "content-v1",
              sections: [],
              outline: [],
              mark_set: { marks: [] },
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            reviewType: "visual",
            sourceVersion: "visual-authoritative-v2",
            url: "http://127.0.0.1:43124/#token=independent-token",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const client = createBrowserReviewClient({ navigate });
    await client.connect();

    await client.switchReview("visual");

    expect(fetchMock).toHaveBeenLastCalledWith("/api/switch", {
      method: "POST",
      headers: {
        authorization: "Bearer short-lived-token",
        "content-type": "application/json",
      },
      body: JSON.stringify({ reviewType: "visual" }),
    });
    expect(navigate).toHaveBeenCalledWith(
      "http://127.0.0.1:43124/#token=independent-token",
    );
  });
});
