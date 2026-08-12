import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

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
  const requiredTools = [
    "add_ai_ppt_material",
    "commit_ai_ppt_artifact",
    "confirm_ai_ppt_gate",
    "confirm_ai_ppt_mission",
    "create_ai_ppt_project",
    "get_ai_ppt_project_snapshot",
    "get_ai_ppt_sidebar_projection",
    "get_delivery_status_projection",
    "open_ai_ppt_browser_review",
    "read_ai_ppt_project_asset",
    "record_chat_delivery",
    "record_internal_gate",
    "reopen_ai_ppt_scope",
    "request_ai_ppt_agent_action",
    "save_ai_ppt_mission_draft",
    "save_review_marks",
    "submit_ai_ppt_human_decision",
  ];
  if (toolNames.length !== 17) {
    throw new Error(`Expected 17 pure-data tools, found ${toolNames.length}.`);
  }
  for (const name of requiredTools) {
    if (!toolNames.includes(name)) {
      throw new Error(`${name} not found. Tools: ${toolNames.join(", ")}`);
    }
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
  const sidebarResult = await client.callTool({
    name: "get_ai_ppt_sidebar_projection",
    arguments: { projectRoot: selectedProjectRoot, initialSpace: "overview" },
  });
  const sidebarCode = sidebarResult.structuredContent?.error?.code;
  if (sidebarResult.isError !== true || sidebarCode !== "HOST_SIDEBAR_UNAVAILABLE") {
    throw new Error("Missing host sidebar must be reported as HOST_SIDEBAR_UNAVAILABLE.");
  }

  const browserResult = await client.callTool({
    name: "open_ai_ppt_browser_review",
    arguments: {
      projectRoot: selectedProjectRoot,
      reviewType: "content",
      sourceVersion: "probe-unproven-source",
    },
  });
  const browserCode = browserResult.structuredContent?.error?.code;
  if (browserResult.isError !== true || browserCode !== "BROWSER_REVIEW_UNAVAILABLE") {
    throw new Error("Missing Browser adapter must be reported as BROWSER_REVIEW_UNAVAILABLE.");
  }

  process.stdout.write(
    `${JSON.stringify(
      {
        ok: true,
        tool_count: toolNames.length,
        tools: toolNames,
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
        sidebar: {
          status: "unavailable",
          code: sidebarCode,
          proofEligible: false,
          realHostEvidence: false,
        },
        browser: {
          status: "unavailable",
          code: browserCode,
          proofEligible: false,
          realHostEvidence: false,
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
