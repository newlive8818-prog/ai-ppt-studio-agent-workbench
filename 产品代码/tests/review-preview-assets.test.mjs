import assert from "node:assert/strict";
import test from "node:test";

import { loadProjectionPreviewAssets } from "../scripts/review-preview-assets.mjs";

test("preview assets read every and only explicit closed projection ref", () => {
  const reads = [];
  const assets = loadProjectionPreviewAssets({
    projectRoot: "/project",
    review: {
      slides: [{ material_views: [{ asset_ref: "content.png" }] }],
      anchors: [{ current_asset_ref: "current.png", previous_asset_ref: "previous.png" }],
      nested: { private_asset_ref: "private.png" },
    },
    readAsset: ({ projectRoot, assetRef }) => (reads.push([projectRoot, assetRef]), { assetRef }),
  });
  assert.deepEqual(reads, [["/project", "content.png"], ["/project", "current.png"], ["/project", "previous.png"]]);
  assert.deepEqual(Object.keys(assets), ["content.png", "current.png", "previous.png"]);
});

test("preview assets propagate reader failures without swallowing them", () => {
  for (const error of [
    Object.assign(new Error("missing asset"), { code: "ENOENT" }),
    Object.assign(new Error("traversal rejected"), { code: "ASSET_PATH_INVALID" }),
    Object.assign(new Error("manifest mismatch"), { code: "PROJECT_MANIFEST_INVALID" }),
    Object.assign(new Error("too large"), { code: "ASSET_TOO_LARGE" }),
  ]) {
    assert.throws(() => loadProjectionPreviewAssets({
      projectRoot: "/project",
      review: { slides: [{ material_views: [{ asset_ref: "required.png" }] }] },
      readAsset: () => { throw error; },
    }), (caught) => caught === error);
  }
});

test("preview assets do not call the reader for absent or null optional refs", () => {
  let reads = 0;
  assert.deepEqual(loadProjectionPreviewAssets({
    projectRoot: "/project",
    review: { slides: [{ material_views: [] }], anchors: [{ previous_asset_ref: null }] },
    readAsset: () => { reads += 1; },
  }), {});
  assert.equal(reads, 0);
});
