import { z } from 'zod';
import { registerCatalogGroup } from '../tool-catalog.mjs';

const id = z.string().trim().min(1);
const hash = z.string().regex(/^[0-9a-f]{64}$/);
const base64 = z.string().min(4).regex(/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/);
const revision = { projectRoot: id, expectedRevision: z.number().int().nonnegative() };
const request = { ...revision, requestId: id };
const object = z.record(z.string(), z.unknown());
const contract = (title, inputSchema, readOnly = false, openWorld = false) => ({
  title, description: `${title}. Existing PPTX source-bound route; the Python runtime validates current heads and exact artifacts.`,
  inputSchema, annotations: { readOnlyHint: readOnly, destructiveHint: false,
    idempotentHint: readOnly, openWorldHint: openWorld },
});
const selection = z.object({
  slide_id: id, request_id: id, review_ref: id, composition_ref: id.optional(),
}).strict();
const relationshipConstraint = z.object({
  kind: z.enum(['overlapping-peers', 'dual-direction', 'belongs-to']),
  source_item_ids: z.array(id).min(1).max(16),
  target_item_ids: z.array(id).max(1),
}).strict();
const sourceMediaRoleBinding = z.object({
  picture_object_id: id,
  text_item_ids: z.array(id).min(1).max(4),
}).strict();
const schemas = {
  begin_existing_deck_optimization: contract('Bind existing PPTX source', {
    ...revision, sourceId: id, sourcePptxSha256: hash, userMessageRef: id,
  }),
  set_existing_deck_external_scope: contract('Record authorized existing-deck CRS scope', {
    ...revision, userMessageRef: id,
    allowedPageOrders: z.array(z.number().int().positive()).min(1),
    excludedImageSha256: z.array(hash), excludedTextItemIds: z.array(id),
  }),
  register_existing_deck_image_request: contract('Register one source-bound CRS design request', {
    ...request, slideId: id, titleItemId: id, commonRules: object,
    layoutMode: z.enum(['standard', 'blank-media-slots', 'client-logo-gallery-20', 'source-media-guided',
      'single-main-screenshot-focus']).optional(),
    requiredVisibleItemIds: z.array(id).max(32).optional(),
    relationshipConstraints: z.array(relationshipConstraint).max(16).optional(),
    sourceMediaRoleBindings: z.array(sourceMediaRoleBinding).max(64).optional(),
    mainSourcePictureObjectId: id.optional(),
  }),
  register_existing_deck_historical_design: contract('Register exact historical design bytes', {
    ...request, slideId: id, titleItemId: id, commonRules: object,
    imageDataBase64: base64, imageSha256: hash, sourcePptxSha256: hash,
    pageOrder: z.number().int().positive(), historicalRequestId: id,
    historicalRequestSha256: hash, historicalResponseSha256: hash,
    historicalReceiver: z.literal('CRS'), historicalModel: z.literal('gpt-image-2'),
    historicalQuality: z.enum(['low', 'medium', 'high']),
  }),
  execute_existing_deck_image_request: contract('Execute one registered CRS design request', request, false, true),
  recover_existing_deck_image_request: contract('Recover one registered CRS design request without resending', {
    projectRoot: id, requestId: id,
  }, true),
  withdraw_existing_deck_unsent_request: contract('Withdraw a never-sent design request', {
    ...request, reason: id,
  }),
  supersede_existing_deck_response: contract('Retire one unselected completed design', {
    ...request, reason: id,
  }),
  register_existing_deck_local_media_composition: contract('Compose exact original media locally', {
    ...request, placements: z.array(object).min(1),
  }),
  review_existing_deck_image_response: contract('Record independent design source review', {
    ...request, reviewerTaskId: id, producerTaskId: id, checks: object,
  }),
  select_existing_deck_images_internal: contract('Select exact reviewed design for every source page', {
    ...revision, reviewerTaskId: id, selections: z.array(selection).min(1),
  }),
  register_existing_deck_native_plan: contract('Register complete region and native-object mapping', {
    ...revision, inventory: object, objects: z.array(z.array(object)).min(1),
  }),
  compile_existing_deck_native_handoff: contract('Compile exact Codex Presentations handoff', {
    ...revision, taskId: id, planRef: id,
  }, true),
  register_existing_deck_native_result: contract('Register source-sized native PPTX result', {
    ...revision, taskId: id, planRef: id, output: object,
  }),
  register_existing_deck_target_evidence: contract('Register same-PPTX PowerPoint evidence', {
    ...revision, resultRef: id, payload: object,
  }),
  register_existing_deck_full_deck_qa: contract('Register complete page-by-page QA', {
    ...revision, resultRef: id, reviewerTaskId: id, pages: z.array(object).min(1),
    targetEnvironment: object,
  }),
  get_existing_deck_optimization_status: contract('Get existing-deck workflow status', {
    projectRoot: id,
  }, true),
  preview_existing_deck_design_image: contract('Preview the exact current existing-deck design', {
    projectRoot: id, requestId: id,
  }, true),
};

export function registerOptimizationTools(server, handlers) {
  registerCatalogGroup(server, 'optimization', schemas, handlers);
}
