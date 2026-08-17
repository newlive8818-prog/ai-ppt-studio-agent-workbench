import { readProjectAsset } from "../mcp/project-asset.mjs";
import { collectProjectionAssetRefs } from "../mcp/review-bridge.mjs";

export function loadProjectionPreviewAssets({
  review,
  projectRoot,
  readAsset = readProjectAsset,
}) {
  const assets = {};
  for (const assetRef of collectProjectionAssetRefs(review)) {
    assets[assetRef] = readAsset({ projectRoot, assetRef });
  }
  return assets;
}
