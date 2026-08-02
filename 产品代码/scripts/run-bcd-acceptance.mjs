import { spawnSync } from "node:child_process";
import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const referenceProject = process.env.AI_PPT_ACCEPTANCE_REFERENCE || "/Users/defei/Documents/AI-PPT-Workspace/projects/ai-ppt-studio-智慧园区冒烟项目-c8a82730";
const runtimeEntry = path.join(root, "skills", "ai-ppt-studio", "scripts", "ai_ppt_runtime.py");

function unwrapArtifact(file) {
  return JSON.parse(file).payload;
}

function initProject() {
  const result = spawnSync(
    "python3",
    [runtimeEntry, "init", "--name", `AI PPT Studio BCD 端到端验收 ${Date.now()}`],
    { cwd: root, encoding: "utf8" },
  );
  if (result.status !== 0) throw new Error(result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);
  return payload.project.project_root;
}

const projectRoot = initProject();
const sourcePayloads = {
  blueprint: unwrapArtifact(await readFile(path.join(referenceProject, "blueprint/content-blueprint/v0001.json"), "utf8")),
  visualBrief: unwrapArtifact(await readFile(path.join(referenceProject, "visual/visual-brief/v0001.json"), "utf8")),
  concepts: unwrapArtifact(await readFile(path.join(referenceProject, "visual/concept-set/v0001.json"), "utf8")),
  visualContract: unwrapArtifact(await readFile(path.join(referenceProject, "visual/visual-contract/v0001.json"), "utf8")),
  sceneGraph: unwrapArtifact(await readFile(path.join(referenceProject, "scene-graph/slide-scene-graph/v0001.json"), "utf8")),
};

await mkdir(path.join(projectRoot, "renders"), { recursive: true });
await mkdir(path.join(projectRoot, "ppt", "rendered"), { recursive: true });
await mkdir(path.join(projectRoot, "ppt", "qa"), { recursive: true });
await cp(path.join(referenceProject, "managed-assets/local/87de47c2-9262-4b6a-9c18-a3b5c4753ae3/exec-1e842a9c-b380-4274-9fb0-3314d452e9aa.png"), path.join(projectRoot, "renders", "concept-a.png"));
await cp(path.join(referenceProject, "renders/engineering-architecture.png"), path.join(projectRoot, "renders", "concept-b.png"));
await cp(path.join(referenceProject, "renders/engineering-closed-loop.png"), path.join(projectRoot, "renders", "engineering-closed-loop.png"));
await cp(path.join(referenceProject, "renders/engineering-architecture.png"), path.join(projectRoot, "renders", "engineering-architecture.png"));
await cp(path.join(referenceProject, "ppt/智慧园区运营中台解决方案-可编辑演示.pptx"), path.join(projectRoot, "ppt", "智慧园区运营中台解决方案-可编辑演示.pptx"));
await cp(path.join(referenceProject, "ppt/qa/delivery-validation.json"), path.join(projectRoot, "ppt", "qa", "delivery-validation.json"));
for (let index = 1; index <= 6; index += 1) {
  const number = String(index).padStart(2, "0");
  await cp(path.join(referenceProject, "ppt", "rendered", `slide-${number}.png`), path.join(projectRoot, "ppt", "rendered", `slide-${number}.png`));
}

const client = new Client({ name: "ai-ppt-bcd-acceptance", version: "0.4.0" });
const transport = new StdioClientTransport({ command: "node", args: ["./scripts/start-mcp.mjs"], cwd: root });
await client.connect(transport);

let snapshot;
const operations = [];
async function tool(name, args) {
  const result = await client.callTool({ name, arguments: args });
  if (result.isError) throw new Error(result.content?.[0]?.text || `${name} failed`);
  const structured = result.structuredContent;
  if (structured?.snapshot) snapshot = structured.snapshot;
  operations.push({ name, revision: snapshot?.revision, gate: snapshot?.gate_state?.current_gate });
  return structured;
}
async function write(name, args) {
  return tool(name, { projectRoot, expectedRevision: snapshot.revision, ...args });
}
async function task(actionType, targetRefs, instructions) {
  const result = await write("request_ai_ppt_agent_action", { actionType, targetRefs, instructions });
  return result.decision.task_id;
}
async function commit(kind, payload, taskId) {
  return write("commit_ai_ppt_artifact", { kind, payload, ...(taskId ? { taskId } : {}) });
}

try {
  await tool("get_ai_ppt_project_snapshot", { projectRoot });
  const materials = [];
  materials.push(await write("add_ai_ppt_material", { materialType: "text", value: "园区已有安防、能耗、工单、招商与资产系统，但跨系统事件仍依赖电话和表格协调。", label: "客户现状" }));
  materials.push(await write("add_ai_ppt_material", { materialType: "url", value: "https://example.com/user-provided-meeting-note", label: "用户提供的会议纪要链接" }));
  materials.push(await write("add_ai_ppt_material", { materialType: "bytes", dataBase64: Buffer.from("一期目标：连接关键系统，形成事件闭环，并在六个月完成三次可验收价值递进。", "utf8").toString("base64"), filename: "一期目标.txt", mimeType: "text/plain" }));
  const sourceRefs = materials.flatMap((item) => item.decision.source_refs);
  const sourceIds = sourceRefs.map((ref) => path.basename(ref, ".json"));

  const classifyTask = await task("classify-materials", ["artifact://material-findings"], "自动分类用户提供的文字、文件和链接，并形成可追溯提炼结果。");
  await commit("material-findings", {
    summary: "3 份用户材料已自动归类为客户现状、会议背景与建设目标，并提炼为蓝图可引用证据。",
    source_assignments: sourceIds.map((sourceId, index) => ({ source_id: sourceId, summary: ["客户现状与核心矛盾", "用户提供的会议背景链接", "一期建设目标与验收节奏"][index], purposes: index === 0 ? ["客户事实", "问题判断"] : index === 1 ? ["会议背景"] : ["建设目标", "路线图"], status: "classified" })),
    findings: sourceRefs.map((sourceRef, index) => ({ finding_id: `F0${index + 1}`, finding_type: index === 0 ? "fact" : index === 1 ? "context" : "goal", content: ["多套系统已建成，但事件无法跨系统闭环。", "存在用户提供的会议纪要链接，可在后续人工授权访问时补充细节。", "一期需要在六个月内形成三次可验收价值递进。"][index], source_ref: sourceRef, locator: index === 1 ? "URL" : "全文", fact_status: index === 1 ? "source-link" : "source-fact", purposes: index === 0 ? ["S02", "S03"] : index === 1 ? ["项目背景"] : ["S06"] })),
    conflicts: [],
    gaps: ["会议纪要链接未主动抓取，符合仅使用用户提供内容的边界"],
  }, classifyTask);

  await commit("mission", { title: "智慧园区运营中台解决方案", audience: "园区管委会领导、运营负责人和信息化负责人", goal: "确认一期建设路径并启动项目", context: "阅读优先的售前解决方案汇报", decision_start: "不推倒重来，以统一事件闭环连接既有系统" });
  const blueprintTask = await task("generate-blueprint", ["artifact://content-blueprint"], "先固定六页内容、目标、逐字稿与来源，不讨论视觉风格。");
  const blueprint = structuredClone(sourcePayloads.blueprint);
  blueprint.slides = blueprint.slides.map((slide, index) => ({ ...slide, source_refs: [sourceRefs[index % sourceRefs.length]], material_refs: [sourceRefs[index % sourceRefs.length]] }));
  await commit("content-blueprint", blueprint, blueprintTask);
  await write("confirm_ai_ppt_gate", { gate: "G0" });

  await commit("visual-brief", sourcePayloads.visualBrief);
  const conceptTask = await task("explore-concepts", ["artifact://concept-set"], "使用 Image 2 形成两个结构不同的视觉构想，不把位图当作最终 PPTX。");
  const concepts = structuredClone(sourcePayloads.concepts);
  concepts.directions[0].sample_image = "renders/concept-a.png";
  concepts.directions[1].sample_image = "renders/concept-b.png";
  await commit("concept-set", concepts, conceptTask);
  await write("submit_ai_ppt_human_decision", { targetRef: "concept://direction", choice: "A", feedback: "端到端验收选择方向 A；验证人工决策链。" });
  await write("confirm_ai_ppt_gate", { gate: "G1" });

  const engineeringTask = await task("build-engineering-samples", ["artifact://engineering-samples"], "使用 Codex Presentations 完成高难关系页与内容复杂页的原生可编辑工程样张并渲染。");
  await commit("engineering-samples", {
    summary: "两张关键页已从视觉构想还原为原生可编辑 PPTX 工程样张。",
    samples: [
      { sample_id: "E01", slide_refs: ["S03"], render_ref: "renders/engineering-closed-loop.png", native_element_ratio: 0.96, editable: true, notes: "闭环关系、文字与连接线均为原生可编辑对象" },
      { sample_id: "E02", slide_refs: ["S04"], render_ref: "renders/engineering-architecture.png", native_element_ratio: 0.97, editable: true, notes: "四层架构、层级标题与说明文字均为原生可编辑对象" },
    ],
    native_coverage: { text: true, shape: true, chart: true, image_crop: true, whole_slide_bitmap: false },
    qa_status: "passed",
  }, engineeringTask);
  await write("confirm_ai_ppt_gate", { gate: "G2" });

  const contractTask = await task("freeze-visual-contract", ["artifact://visual-contract", "artifact://slide-scene-graph"], "固化视觉合同和逐页 Scene Graph，约束全稿原生实现。");
  await commit("visual-contract", sourcePayloads.visualContract);
  await commit("slide-scene-graph", sourcePayloads.sceneGraph, contractTask);
  await write("confirm_ai_ppt_gate", { gate: "G3" });

  const buildTask = await task("build-pptx", ["artifact://presentation-handoff", "artifact://delivery"], "使用 Codex Presentations 制作完整可编辑 PPTX，渲染每页并运行 QA。");
  await commit("presentation-handoff", { content_blueprint_ref: "blueprint/content-blueprint/v0001.json", visual_contract_ref: "visual/visual-contract/v0001.json", scene_graph_ref: "scene-graph/slide-scene-graph/v0001.json", output_pptx: "ppt/智慧园区运营中台解决方案-可编辑演示.pptx", render_directory: "ppt/rendered", source_notes_ref: "ppt/qa/delivery-validation.json", slide_count: 6, execution_layer: "Codex Presentations / @oai/artifact-tool", editability_contract: { native_business_content: true, replaceable_complex_art: true, whole_slide_bitmap: false } });
  await commit("delivery", { pptx: "ppt/智慧园区运营中台解决方案-可编辑演示.pptx", renders: Array.from({ length: 6 }, (_, index) => `ppt/rendered/slide-${String(index + 1).padStart(2, "0")}.png`), slide_count: 6, qa_status: "passed", validation_ref: "ppt/qa/delivery-validation.json", sources: sourceRefs, editable: true }, buildTask);
  await write("confirm_ai_ppt_gate", { gate: "G4" });

  if (!Object.values(snapshot.gate_state.gates).every((value) => value === "passed")) throw new Error("Not all quality gates passed");
  if (snapshot.space_projections.materials.status !== "classified") throw new Error("Materials projection is not classified");
  if (snapshot.space_projections.blueprint.slide_count !== 6) throw new Error("Blueprint does not contain six slides");
  if (snapshot.space_projections.visual.engineering_samples.length !== 2) throw new Error("Engineering samples are missing");
  if (!snapshot.space_projections.delivery.pptx_exists || snapshot.space_projections.delivery.render_count !== 6) throw new Error("Delivery evidence is incomplete");

  const report = {
    ok: true,
    acceptedAt: new Date().toISOString(),
    projectRoot,
    revision: snapshot.revision,
    gates: snapshot.gate_state.gates,
    spaces: {
      materials: { status: snapshot.space_projections.materials.status, sources: snapshot.space_projections.materials.source_count, findings: snapshot.space_projections.materials.findings.length },
      blueprint: { status: snapshot.space_projections.blueprint.status, slides: snapshot.space_projections.blueprint.slide_count },
      visual: { status: snapshot.space_projections.visual.status, directions: snapshot.space_projections.visual.direction_count, engineeringSamples: snapshot.space_projections.visual.engineering_samples.length, sceneGraphs: snapshot.space_projections.visual.scene_graph_coverage },
      delivery: { status: snapshot.space_projections.delivery.status, pptx: snapshot.space_projections.delivery.pptx_ref, renders: snapshot.space_projections.delivery.render_count, qa: snapshot.space_projections.delivery.qa_status, editable: snapshot.space_projections.delivery.editable, wholeSlideBitmap: snapshot.space_projections.delivery.whole_slide_bitmap },
    },
    operations,
  };
  await mkdir(path.join(root, "output", "acceptance"), { recursive: true });
  await writeFile(path.join(root, "output", "acceptance", "bcd-acceptance.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
} finally {
  await client.close();
}
