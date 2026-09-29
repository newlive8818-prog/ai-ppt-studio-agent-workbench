import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import {
  PUBLIC_TOOL_CATALOG,
  PUBLIC_TOOL_CATALOG_SHA256,
} from "../mcp/tool-catalog.mjs";

const projectRoot = process.env.AI_PPT_PROBE_PROJECT?.trim() || undefined;

const client = new Client({ name: "ai-ppt-studio-probe", version: "0.1.0" });
const transportEnv = Object.fromEntries(
  Object.entries(process.env).filter((entry) => typeof entry[1] === "string"),
);
const transport = new StdioClientTransport({
  command: process.execPath,
  args: ["./scripts/start-mcp.mjs"],
  env: transportEnv,
});

await client.connect(transport);

try {
  const listed = await client.listTools();
  const toolNames = listed.tools.map((tool) => tool.name).sort();
  const expectedNames = PUBLIC_TOOL_CATALOG.map((tool) => tool.name).sort();
  if (new Set(toolNames).size !== toolNames.length) {
    throw new Error(`Duplicate public tool names: ${toolNames.join(", ")}`);
  }
  if (JSON.stringify(toolNames) !== JSON.stringify(expectedNames)) {
    throw new Error(`Public tool catalog drift: ${toolNames.join(", ")}`);
  }
  for (const tool of listed.tools) {
    const metaKeys = Object.keys(tool._meta || {});
    if (
      tool._meta?.ui?.resourceUri ||
      metaKeys.some((key) => key.toLowerCase().includes("outputtemplate"))
    ) {
      throw new Error(`${tool.name} must not attach a chat UI template.`);
    }
  }

  const missionConfirmationTool = listed.tools.find(
    (tool) => tool.name === "confirm_ai_ppt_mission",
  );
  const missionSummaryProperties =
    missionConfirmationTool?.inputSchema?.properties?.missionSummary?.properties || {};
  const missionSummaryExposed = [
    "topic",
    "primaryAudience",
    "desiredJudgmentOrAction",
    "materialSummary",
  ].every((field) => Object.hasOwn(missionSummaryProperties, field));
  if (!missionSummaryExposed) {
    throw new Error(
      "confirm_ai_ppt_mission must expose the complete missionSummary for host-native confirmation.",
    );
  }

  const snapshotResult = await client.callTool({
    name: "get_ai_ppt_project_snapshot",
    arguments: projectRoot ? { projectRoot } : {},
  });
  if (snapshotResult.isError) {
    throw new Error(snapshotResult.content?.[0]?.text || "Snapshot read failed.");
  }
  const initialSnapshot = snapshotResult.structuredContent?.snapshot;
  if (!initialSnapshot?.project?.project_root || !Number.isInteger(initialSnapshot.revision)) {
    throw new Error("Snapshot result is missing project identity or revision.");
  }

  const selectedProjectRoot = initialSnapshot.project.project_root;
  const browserCode = "BROWSER_REVIEW_UNAVAILABLE";
  const requiredReviewTools = [
    "open_or_resume_review_session",
    "get_content_review_projection",
    "get_visual_review_projection",
  ];
  const professionalReviewToolsPresent = requiredReviewTools.every((name) =>
    toolNames.includes(name),
  );

  process.stdout.write(
    `${JSON.stringify(
      {
        ok: true,
        tool_count: toolNames.length,
        tools: toolNames,
        tool_catalog_sha256: PUBLIC_TOOL_CATALOG_SHA256,
        chat_ui: {
          templateCount: 0,
          ordinaryToolsAreDataOnly: true,
          proofEligible: true,
        },
        mission_confirmation: {
          host_native_fallback: true,
          mission_summary_exposed: missionSummaryExposed,
          chat_ui_template: Boolean(
            missionConfirmationTool?._meta?.ui?.resourceUri ||
              Object.keys(missionConfirmationTool?._meta || {}).some((key) =>
                key.toLowerCase().includes("outputtemplate"),
              ),
          ),
        },
        professional_review: {
          review_session: professionalReviewToolsPresent ? "available" : "unavailable",
          content_review_projection: toolNames.includes(
            "get_content_review_projection",
          ),
          visual_review_projection: toolNames.includes(
            "get_visual_review_projection",
          ),
          host_open: {
            status: "unavailable",
            code: browserCode,
            proofEligible: false,
            realHostEvidence: false,
          },
          host_notification: {
            status: "unverified",
            proofEligible: false,
            realHostEvidence: false,
          },
          ai_receipt: {
            status: "unverified",
            proofEligible: false,
            realHostEvidence: false,
          },
        },
        project: {
          name: initialSnapshot.project.name,
          root: selectedProjectRoot,
          revision: initialSnapshot.revision,
        },
      },
      null,
      2,
    )}\n`,
  );
} finally {
  await client.close();
}
