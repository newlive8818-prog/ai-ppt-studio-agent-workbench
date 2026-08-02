import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const projectRoot = process.env.AI_PPT_PROBE_PROJECT?.trim() || undefined;
const writeProbe = process.env.AI_PPT_PROBE_WRITE === "1";
if (writeProbe && !projectRoot) {
  throw new Error("AI_PPT_PROBE_PROJECT is required when AI_PPT_PROBE_WRITE=1.");
}

const client = new Client({ name: "ai-ppt-studio-probe", version: "0.1.0" });
const transport = new StdioClientTransport({
  command: "node",
  args: ["./scripts/start-mcp.mjs"],
});

await client.connect(transport);

try {
  const listed = await client.listTools();
  const toolNames = listed.tools.map((tool) => tool.name).sort();
  const requiredTools = [
    "get_ai_ppt_project_snapshot",
    "render_ai_ppt_workbench",
    "submit_ai_ppt_human_decision",
  ];
  for (const name of requiredTools) {
    if (!toolNames.includes(name)) {
      throw new Error(`${name} not found. Tools: ${toolNames.join(", ")}`);
    }
  }

  const renderResult = await client.callTool({
    name: "render_ai_ppt_workbench",
    arguments: {
      ...(projectRoot ? { projectRoot } : {}),
      initialSpace: "overview",
      requestedDisplayMode: "inline",
    },
  });
  if (renderResult.isError) {
    throw new Error(renderResult.content?.[0]?.text || "Workbench render failed.");
  }
  if (
    renderResult._meta?.["openai/outputTemplate"] !==
    "ui://ai-ppt-studio/workbench.html"
  ) {
    throw new Error("Render result did not include the expected output template.");
  }

  const resource = await client.readResource({
    uri: "ui://ai-ppt-studio/workbench.html",
  });
  const resourceEntry = resource.contents?.[0];
  const widgetHtml = resourceEntry?.text || "";
  if (resourceEntry?.mimeType !== "text/html;profile=mcp-app") {
    throw new Error(`Unexpected widget MIME type: ${resourceEntry?.mimeType}`);
  }
  if (!widgetHtml.includes('id="root"') || widgetHtml.length < 50_000) {
    throw new Error("Widget resource does not contain the built application shell.");
  }
  if (
    /<script\b[^>]+\bsrc=["']https?:\/\//i.test(widgetHtml) ||
    /<link\b[^>]+\bhref=["']https?:\/\//i.test(widgetHtml)
  ) {
    throw new Error("Widget resource must be self-contained without network scripts or styles.");
  }
  if (/<script\b[^>]*\btype=["']module["']/i.test(widgetHtml)) {
    throw new Error("Widget resource must not contain module scripts.");
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

  let writeResult = null;
  if (writeProbe) {
    const decision = initialSnapshot.current_decision;
    const choice =
      decision.options?.find((option) => option === decision.recommended_choice) ||
      decision.options?.[0] ||
      "继续推进";
    const submitted = await client.callTool({
      name: "submit_ai_ppt_human_decision",
      arguments: {
        projectRoot,
        expectedRevision: initialSnapshot.revision,
        targetRef: decision.target_ref,
        choice,
        feedback: "Phase A MCP 双向回写验收；不代表真实业务决策。",
      },
    });
    if (submitted.isError) {
      throw new Error(submitted.content?.[0]?.text || "Decision write failed.");
    }
    const refreshed = submitted.structuredContent?.snapshot;
    if (refreshed?.revision !== initialSnapshot.revision + 1) {
      throw new Error("Decision write did not advance the project revision exactly once.");
    }
    if (!submitted.structuredContent?.follow_up_message) {
      throw new Error("Decision write did not return a Codex follow-up message.");
    }

    const staleWrite = await client.callTool({
      name: "submit_ai_ppt_human_decision",
      arguments: {
        projectRoot,
        expectedRevision: initialSnapshot.revision,
        targetRef: decision.target_ref,
        choice,
      },
    });
    if (
      staleWrite.isError !== true ||
      staleWrite.structuredContent?.error?.code !== "REVISION_CONFLICT"
    ) {
      throw new Error("Stale revision write was not rejected with REVISION_CONFLICT.");
    }
    writeResult = {
      revisionBefore: initialSnapshot.revision,
      revisionAfter: refreshed.revision,
      staleWriteCode: staleWrite.structuredContent.error.code,
    };
  }

  process.stdout.write(
    `${JSON.stringify(
      {
        ok: true,
        tools: toolNames,
        widget: {
          uri: "ui://ai-ppt-studio/workbench.html",
          mimeType: resourceEntry.mimeType,
          bytes: Buffer.byteLength(widgetHtml, "utf8"),
          selfContained: true,
        },
        project: {
          name: initialSnapshot.project.name,
          root: initialSnapshot.project.project_root,
          revision: initialSnapshot.revision,
        },
        writeProbe: writeResult,
      },
      null,
      2,
    )}\n`,
  );
} finally {
  await client.close();
}
