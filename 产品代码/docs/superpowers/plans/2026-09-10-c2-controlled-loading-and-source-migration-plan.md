# C2 受控加载、宿主预检与来源迁移实施方案

> **For agentic workers:** 受控实施时使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 按任务执行。本文件为受控实施方案；审查结果和启动状态见唯一台账。复选项不是已执行记录，总控安排前不执行下列变更。

**Goal:** 从已审 A/B 固定候选形成完整的桌面 Plugin，核验真实宿主进程，并在保持三页原文与用户决定的前提下，把 revision 19 的来源引用迁移到正式 finding。

**Architecture:** 同一 CHG-IL-C2、`codex/image-led-native-anchors` 与 28a9 Worktree，按“打包修复候选 → 受控加载及只读宿主预检 → finding 登记检查点 → 新内容链及版本审核”推进。来源证据只复用当前 inventory；Image 2 负责正文设计，定版后的确切图片与绑定文案继续约束原生转换。

**Tech Stack:** 现有 Node MCP、Python Runtime、标准库 Image 2 wrapper、Plugin release builder/verifier、正式内容服务与 ReviewSession/G0 合同。

本轮授权来自总控任务 `01a07cae-3eae-7d12-abc5-eaa73addf881` 对 B 提交的核验后派发：**只读准备方案、固定文档和独立 Review**。本轮不实施打包源码修复、不生成后继包、不安装或改宿主配置、不执行真实 helper/HTTP、不发布 EvidenceBook/Blueprint、不迁移客户 Runtime。实施阶段由总控另行安排，沿用既有 Change 和同范围材料授权；不重新索取已认可材料、71 段文案或设计共同规范。

执行事实仅进入[唯一 C2 台账](../../validation/c2-image-led/verification-report.md)。本方案及附件是计划和证据，不建立第二业务状态或素材事实源。

## 1. 当前固定身份与证明边界

| 对象 | 本轮核定身份 | 含义 |
|---|---|---|
| A 来源恢复 | `7b0a24a1ac1e568ccb0a9af18a018fbf052dec93` | 已实现、测试、独立 Review、本地提交；不是已加载 |
| B 供应方准备 | `fe3fb613673c0c70e7633a384252939365d9b7fa` | 总控已接纳进入集成准备；本方案源码基准 |
| B 11 文件 freeze | `fef15d41bb64a561b051d26b7783e4eace04afa0fe7deacb056f007f43e6be8c` | [最终清单](../../validation/c2-image-led/source-recovery-implementation/provider-code-freeze-final.json) |
| B 包装器 | `855fbb788400c0586b7d669560f048d19ccb0f4048e3606c7e67f686ad66ac20` | 后继包必须保持，除非另有明确受审实现修改 |
| B Plugin 原始压缩包 | `109716058e8bc13cfcbae726802ebea4b0d250c89b7a9d21d94e7e77944d254d` | `/private/tmp/c2-provider-preparation-validation-ztxhptxc/c2-provider-b-plugin.tar.gz`；原样保留 |
| B Plugin manifest | `5dfb4afa30c4a625390f999ef28bdc4954ef9a0349883dee8f11f61c48fc2687` | 3763 项 hash；仍漏原生脚本，不能直接作为完整 native 加载候选 |
| 当前客户 | revision `19`，G0=`passed`，G1=`open`，G2–G4=`locked` | 本轮真实 MCP 默认 snapshot 已读取；见[真实快照](../../validation/c2-image-led/loading-migration-preparation/native-snapshot.json) |
| 当前 state | SHA256 `9119919e9090e028d28e948664e24762714d9b1476544e38cd645e148d175de9`；mtime_ns `1789007522156646754` | 只表示 state 文件身份，不扩张为整棵客户 Runtime 对比 |

**本轮没有可冒称已经完整就绪的新加载包。** 固定 B 原始包是后继构建的审查基准；拟加载目标为“B + 第 2 节最小打包修复”的独立 Plugin 包。后继源码 commit、安装版本、manifest 和压缩包 hash 必须在修复与验证完成后真实生成，再由总控核定；不得编造未来 hash，或先修改 B 包再沿用旧身份。

### 1.1 当前宿主身份与尚未证明项

当前注入 Skill 路径与磁盘 cache 都指向 `0.4.0+codex.c2.cfabfc1.20260910`。该 cache 的 `mcp/server.mjs` SHA256=`cfa8c8b24d838dc4f9b7e8917a5beb7614a12b7e3a9e7733efb75a972d1ef79c`，release manifest=`718e1cb8bb879c4df642f1a7cffce0b50f8854d7185b11a556bc8025d7a793c8`；新 `image2_crs.py` 不存在，原生脚本却存在，hash=`1c81e15666656bc6422b06db4481dd934f1ac10c7a47455840645e51a86eca14`，来源是历史 cfab 同提交补件。不能把“当前老 cache 有脚本”推成“B builder 已修复”。

[进程及磁盘核查](../../validation/c2-image-led/loading-migration-preparation/host-files-and-processes.json)观察到 5 个 Node 进程共用该 cache cwd。05:15:20–05:15:21 UTC 的真实 snapshot 调用窗口中，[短时采样](../../validation/c2-image-led/loading-migration-preparation/host-snapshot-process-correlation.json)只观察到父 PID `48151` 下的 Python PID `65838`，其可执行程序位于 Python 3.14 Framework。这是时间相关的当前进程证据，不是 MCP 请求与 PID 的密码学绑定，也不证明 Python `sys.executable` 的精确拼写或其环境变量；PID 后续变化是正常情况，执行时重新记录。

默认 snapshot 没有供应方预检字段。真实当前 MCP 的新 `includeImage2Preflight`、四键 presence、wrapper nonce/hash仍未建立，不能拿 shell 或临时 MCP 结果补写成功。实际新包加载后以第 3 节真实工具回执建立这些证明。

## 2. Task L1：先关闭 Plugin 原生脚本发布缺口（待总控安排实施）

**未来修改文件：** `产品代码/scripts/build-plugin-release.mjs`、`产品代码/scripts/verify-plugin-release.mjs`、`产品代码/tests/plugin-release.test.mjs`、`产品代码/tests/image2-provider-preflight.test.mjs`。不修改 renderer 布局算法、目标绑定、区域映射、内容或现有审核 UI。

- [ ] 在 release builder 的 `ALLOWLIST` 加入确切一项：

```javascript
["scripts/image-led-native.mjs", "scripts/image-led-native.mjs"],
```

- [ ] 在 verifier 和发布完整性测试的 required 文件数组中加入：

```javascript
"scripts/image-led-native.mjs",
```

- [ ] 先添加会在 B 基准失败的真实打包断言：包内脚本存在、字节/hash等于固定源码；两次重建 manifest 一致。负例在临时包删除脚本后**重新计算合法 manifest**，再调用 `verifyPluginRelease`，仍必须以缺少 required file 拒绝，不能只依赖旧 manifest 与缺文件不相等的泛化失败。

```javascript
await rm(path.join(brokenPlugin, "scripts/image-led-native.mjs"));
await refreshPluginReleaseManifest(brokenPlugin);
await assert.rejects(
  verifyPluginRelease(brokenPlugin, { validator: false, probe: false }),
  /Release is missing required file: scripts\/image-led-native\.mjs/,
);
```

以上 `brokenPlugin` 必须是本测试新建的隔离包副本；导入 `rm` 和现有 `refreshPluginReleaseManifest`。此处关闭 validator/probe 只用于隔离负例，正式候选仍执行完整发布验证。

- [ ] 在现有临时包测试中，从**包内** `scripts/image-led-native.mjs` 动态导入 `preflight` / `render`，复用 `tests/fixtures/image-led-synthetic.mjs::syntheticHandoff`。使用规范化临时项目路径、显式 Python 与 bundled Node module root；从包外 cwd、无调用方 `PYTHONPATH` 启动。完整合成 handoff 的 preflight 成功且无输出目录；改字、错 target hash、缺映射、越界输出各自失败，SDK load counter 为 0，既有文件不变。该脚本是导出函数模块，没有可假定存在的 `--preflight` CLI；不能把直接运行文件后 exit 0 当作预检通过。
- [ ] 在完整成品包上执行三页合成`render`及该包的`verifyOutputSnapshots`，重新读取本次PPTX/比较图，并核对3页与PPTX hash。另在可丢弃包副本覆盖脚本篡改、缺包内Python域依赖、缺外部SDK及已有输出保护；不能回取原仓库模块补齐。合成输出只能标为工程产物，视觉、PowerPoint与用户验收仍为NotEstablished。
- [ ] 采用[打包审计](../../validation/c2-image-led/loading-migration-preparation/packaging-audit.json)的`planned_commands`中P1–P8精确入口；P6合成脚本本轮仅通过syntax-only检查，尚未执行。原生依赖中的skia-canvas位于artifact-tool内嵌目录，只核过路径可解析，不冒称真实导入成功。独立Skill的S1/S2明确不属于此轮实施。
- [ ] `.mcp.json` 仍声明 B 的四键；固定 wrapper、finding 与内容服务源码必须与 B 相同。任何超出上述打包/测试文件的生产 diff 先返回总控审范围。
- [ ] 在私有源码/依赖/offline 缓存运行以下实际入口，保存 RED/GREEN、命令、原始日志 hash。`C2_RUNTIME_NODE_MODULES` 指向 bundled Node dependencies，`C2_RUNTIME_PYTHON` 指向已核定解释器；`TMPDIR=/private/tmp`。Node 进程预检用例另外覆盖默认 macOS TMPDIR，不允许 skip。

```text
node --test tests/plugin-release.test.mjs tests/image2-provider-preflight.test.mjs tests/image-led-native.test.mjs
node --test tests/*.test.mjs
<fixed-bundled-python> -m unittest discover -s tests
node node_modules/typescript/bin/tsc -p widget/tsconfig.json --noEmit
node scripts/build-widget.mjs
node node_modules/vitest/vitest.mjs run
```

工作目录必须是此次隔离验证副本的 `产品代码/`，不是共享 node_modules 的原注册 checkout；依赖复用 B 已验证的私有副本与缓存，禁止自动在线安装。所有独立synthetic probe使用明确最小env，去掉调用方PYTHONPATH/PYTHONHOME及AI_PPT_IMAGE2配置，不继承客户profile或凭据。`<fixed-bundled-python>`为L2列出的bundled Python绝对路径；只在私有全量测试环境补齐测试用YAML，不把临时测试依赖配置到宿主。验证数量按真实修订后的结果记录，不预填仍为 185/754/755。提交前独立 Review、普通 `git diff --check` 不排除日志。

### 2.1 本次只加载 Plugin，Skill 完整 native 不在本轮补做

Plugin 的 Python 目录为 `src/`，renderer 当前 `../src` 定位正确，因此本次无需改原生渲染器。独立 Skill 包虽有 B wrapper，但既没带脚本，renderer 的固定 `../src` 又与 Skill 的 `runtime/` 布局不匹配；只复制脚本不能关闭问题。Skill 原始包保留 A/B 已有证明，不作为此次桌面加载对象，也不宣称支持完整 native。Skill 双布局适配留给后续明确范围，不能混入 Plugin 修复。

### 2.2 冻结后继候选，禁止覆盖 B 包

- [ ] 打包修复通过后先固定精确源码提交；安装版本按“`0.4.0+codex.c2.` + 提交前 7 位 + `.` + 该提交日期 YYYYMMDD”派生，避免与当前 cfab cache 或 B 通用 0.4.0 名称混淆。
- [ ] 从该提交的私有快照构建新 Plugin。版本身份变更仅写入这次新生成的 staging 包元数据，重新计算 manifest 并验证；不得修改 B 原始包或真实安装目录来伪装构建结果。
- [ ] 形成候选清单：完整 commit、源代码逐文件 hash、包版本/规范路径、完整 manifest/hash、压缩包/hash、wrapper/native 脚本 hash、允许的包装元数据差异、验证及独立 Review 身份。确认无本产品第一方测试、客户 Runtime 或客户材料混入包；生产依赖按 lockfile 原始分发内容完整保留，不裁剪第三方依赖自带的测试文件。
- [ ] 总控核定该候选后才进入 L2。若临时文件已消失，按固定 commit 重建并重新验证新包身份；不能沿用已不存在压缩包的旧 hash。

## 3. Task L2：受控加载与真实宿主只读预检（方案审查前不执行）

**本阶段未来可变位置：** 新 Plugin 安装身份、对应 cache、仅本 Plugin 的非敏感环境配置。客户项目路径固定为 `/Users/defei/Documents/AI-PPT-Workspace/projects/c2-image-led-native-anchors-20260909`。当前老版本及其配置先保留恢复点；原恢复备份不是“必然匹配此刻现场”，回滚前核对现场备份身份。

- [ ] 记录当前实际安装/cache、manifest、进程与非敏感配置的恢复点。备份可能含敏感配置时仅在原受控宿主位置保留，不复制到源码/日志，不输出凭据值。
- [ ] 安装 L1 固定的新 Plugin 身份，核对安装/cache逐文件 hash；不手补正在运行的旧目录。安装本身不迁移 Runtime，不重发 Mission，不改现有 Gate。
- [ ] 推荐显式固定 B 全量验证使用过的解释器 `/Users/defei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`，而不是依赖 PATH 的候选顺序。其单独只读探针为 Python 3.12.14、Pillow 可解析；这不是当前 MCP 解释器证据。系统 Python 3.14 普通启动可见 Pillow，隔离启动不可见，进一步说明不能将 shell 能力冒称宿主能力；本方案不安装新依赖或传入临时 `/private/tmp/c2-python-deps`。
- [ ] 在当前 Plugin 的配置中设置 `AI_PPT_PYTHON` 为上述确切解释器，`AI_PPT_PYTHONPATH` 为新包规范化的 `src/`；四键值如下，路径必须由 L1 核定的新安装包真实路径派生，不用 B 临时目录或旧 cfab 路径：

```text
AI_PPT_IMAGE2_ADAPTER_COMMAND = JSON.stringify([exactBridgePython, canonicalNewPluginRoot + "/src/ai_ppt_studio/adapters/image2_crs.py"])
AI_PPT_IMAGE2_RECEIVER = CRS
AI_PPT_IMAGE2_MODEL = gpt-image-2
AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST = []
```

`exactBridgePython` 与 `AI_PPT_PYTHON` 是同一个固定绝对路径；JSON 数组不能加 shell、额外参数或启动钩子。`canonicalNewPluginRoot` 必须取安装实际路径的 realpath，处理 macOS `/var` 与 `/private/var` 别名。若解释器对 `sys.executable` 的实际拼写不同，记录本次已识别进程后修正这两个配置值为一致；不得放宽 wrapper 识别。环境值只配在宿主，不进入客户 Runtime、业务文案或公共工具参数。
- [ ] 让真实 Codex MCP 连接加载新身份。先核对真实工具 schema仍43项、snapshot有可选布尔 `includeImage2Preflight`、finding 分支存在；不能以仅刷新 Skill、另起 shell server 或模拟连接代替。若宿主需要重启，由总控安排其支持的重连/重启流程，不使用禁止操作 Codex 自身的 UI 绕行。
- [ ] 用真实 `get_ai_ppt_project_snapshot` 先不带新选项读取，再以 `includeImage2Preflight=true` 读取同一客户项目。核对普通 snapshot 与原状态，保存真实工具回执的 `configuration_presence`、`known_wrapper=true`、`protocol_probe=passed`、`helper_executable=true`、`probe_nonce` 和 `wrapper_sha256`；hash须匹配 L1 候选与实际包。`external_connection` 必须仍是 `not-tested`。
- [ ] 再次只读调用获得不同 nonce，同一 wrapper hash 与业务状态；将本次当前进程 PID/cwd/入口及安装 manifest 与真实回执共同绑定。nonce来自实际工具，不能自己填入。配置缺失/协议失败/helper不可执行是能力缺口，先修配置或加载，客户材料授权不因此失效。
- [ ] 本地预检通过后停在加载检查点，回传证据由总控安排来源迁移。这个通过不包含认证、CRS 当前参数支持或生图质量，也不执行真实 helper/HTTP。

## 4. Task M1：来源等值清单和正式 finding 登记（待总控安排）

[只读来源审计](../../validation/c2-image-led/loading-migration-preparation/source-migration-audit.json)绑定实际两份源、25个制品及当前19个heads。当前正式finding为0；下表六条是本次按材料角色明确的登记方案，不是schema强制数量下限。页finding可派生精确文字/图片对象，不需要将71段原文分别登记为71条finding。审计中的`registered_ref`及后继版本均为null，必须等待真实回执。

当前 inventory 固定为 `artifact://material-inventory/d588082b32fb2583581a137950bb1bbaf359da01ca5899e40db8c41d1f05df92`。M03为`source-b87fe585d7803c93`、实际源SHA256=`b87fe585d7803c93378e9bb552ef2aac15834bd0b8dc733b19660c896eddd8f0`；M01为`source-6f00739b1d0aea77`、实际源SHA256=`6f00739b1d0aea7724755e781322d9192dabb68ee1b4251da4f4525b975ae070`。均与当前库存一致，不能凭短名重新搜索同名文件。

| 计划键 | 源/正式sourceLocation | contentKind / exclusionMode | 用途 | 实际提取content SHA256 |
|---|---|---|---|---|
| `C2-S04-page-evidence` | M03 `{"kind":"page","page":12}` | `text` / `scope` | declared-page-evidence | `cb594cfa2b9d1238d121537ccfb43ed8bfd8594b56da5c6d63cb9658197b2bf7` |
| `C2-S05-page-evidence` | M01 `{"kind":"page","page":25}` | `text` / `scope` | declared-page-evidence | `80294116d0858fdf289b8663588e2a32c1239b3d7db0efeed50788a76e1f5a72` |
| `C2-S06-page-evidence` | M03 `{"kind":"page","page":18}` | `text` / `scope` | declared-page-evidence | `bbc536664cdaf0980b83687bf465c2821df8d232086d5739a3ac6d7a844c4ddb` |
| `C2-S06-image-33-optional` | M03 `{"kind":"object","page":18,"object_id":"33"}` | `image` / `scope` | declared-optional-real-material | `9a80b77ae22c245f4e92aa32267eaad56334e3e50b7a484d55a7cb8f0e7d19c7` |
| `C2-S06-image-36-optional` | M03 `{"kind":"object","page":18,"object_id":"36"}` | `image` / `scope` | declared-optional-real-material | `c4e39f2a170e5ed5fd56083d6f37bdf8b2d3f47e4ec808e1f5b5d56757f6ddd3` |
| `C2-S06-image-39-excluded` | M03 `{"kind":"object","page":18,"object_id":"39"}` | `image` / `image-content` | excluded-only | `0c19e88a931133dec1b3210f462eb2eccfa5cd762ad2cd5253b000e66bf41f2b` |

三页实际71个精确文字对象与已认可输入、当前EvidenceBook及Blueprint可见文案逐字一致。各页有序字符串数组采用UTF-8紧凑JSON（非整页文本文件字节）的SHA256如下；提取整页文本hash见上表，两种编码不能混称。

| 页面 | 段落数 | 已接受有序可见文案hash |
|---|---|---|
| C2-S04 | 16 | `65ed743ad92fe0aa81d5902ba878c7001a0fc227ad1cc1d3cce7ad494c5cd6e8` |
| C2-S05 | 36 | `8bb43d25f1c50042bd9950ce758cdfcc943ed2e3cb6caea014cb5c4a9ba2dd9a` |
| C2-S06 | 19 | `d1be15c3ca56f7e479ed32440f1e2d663bf55e1ab79e971ad199a7d5fb863c5c` |

共同规范文件`input/confirmed-three-page-input-v1/common-rules.json`的字节SHA256=`3611e3d651a5037634d9a8532ae2b8bf82375bd5b913eeca8aa44e553082144b`，涵盖字体、配色、后备字体、标题栏和背景；三页`body_layout_instructions`均为空，继续保持Image 2正文构图自主性。当前没有正式visual policy/scope head，该状态不代表持续会话授权撤回；后续仍需按既有流程建立有效结构化承接。

审计172项比较中168项直接相等，4项whole-object不等均来自准备稿的窄投影：三页blocks没有当前`identity`，两幅图片的准备views缺少当前来源、用途、处理方式等字段。共享ID/正文/资产完全一致，未解释业务差异为0；迁移以**当前完整四对象**为基准，严禁用准备稿覆盖。71个文字对象selector/hash、144项逐上下文引用映射、当前完整字段hash详见审计，不复制客户正文或图片到产品仓库。

源引用迁移有三种特殊映射：EvidenceBook根`source_refs`由两个库存ID改为五个可用finding真实回执；33/36的material view各绑定自己的对象finding；39只能进入`excluded_material_refs`，不混入usable source refs。S06禁用外推说明保留原文字证据身份与限制，不改绑成允许使用的禁图来源。


- [ ] 迁移前重新读取实际 snapshot、inventory、原始两份 PPTX，核对 state/来源哈希、三页输入版本与本方案事实附件。只要来源、现有 heads、用户决定或业务内容发生变化，就先重新核对差异，不能仍按 revision 19 的固定数值发写入请求。
- [ ] 原地复用当前 inventory 和 Mission，逐项正式调用 `add_ai_ppt_material` 的 finding 分支；使用上表来源清单中的 `sourceId/sourceSha256/sourceLocation/contentKind/exclusionMode`，不使用 text/url/bytes 重登记材料。
- [ ] 每次以真实回执的 `artifact_ref` 建立对应映射，并读取新的 revision。新登记只追加 finding/事件/幂等信息，业务 heads、Mission、inventory、旧内容/G0保持；不把 revision 增加误写为 G0失效，也不假定所有步骤固定为 r20/r21。
- [ ] 公开工具没有 `commandId` 参数。响应丢失时先只读核对事件及其 detached artifact，再通过正式 resolver 核验项目/inventory/真实源 hash与selector；存在有效正式回执时恢复其ref，不凭预测hash冒称已创建。若无法建立是否已登记的确切状态，在本检查点停下交总控，不自动把 shell/Kernel 写入作为恢复办法。
- [ ] 对照登记前后全部业务 heads和Gate；任何超出 finding 登记合同的变化立即停止后续发布。客户历史state不被回滚，已经登记的 detached finding 可保留；不删除事件或手改 revision。

## 5. Task M2：新内容链与版本绑定审核（待总控安排）

**唯一允许技术差异：** 当前库存ID→对应正式finding引用、上游引用随新版本更换、统一新 `source_version`、把已认可的禁用图落实为 `excluded_material_refs`，以及正式服务要求且如实生成的生成元数据/审核时间和身份。具体路径以审计`source_mappings`、`complete_old_inventory_id_occurrences`及`future_migration.allowed_payload_differences`为白名单；行版本仅在合同要求时与统一版本同步。新增来源证据不得改写业务正文、标题、页序、page_task、reading_question、图片用途、共同规范或用户已接受差异。将 `excluded_material_refs=[]` 更正为禁用finding属于明确可审的技术差异，不能声称整个payload字节完全相等。

- [ ] 从当前四对象读取原payload，按正式映射派生新的4份内存/受控项目输入，不让模型重新写一套文案。新source version为此次真实受控迁移的唯一版本标识，四对象一致；引用以各步返回的正式ref顺序绑定。
- [ ] 写入前运行等值检查：三页71段有序逐字文案（16/36/19）、标题/页序/目标/阅读问题、两张允许图片确切字节、禁用图片身份与用途、共同字体/配色/标题栏/背景；除技术白名单外的任何diff均拒绝。记录字段hash/差异路径，不把仅段落数相同说成等值。
- [ ] 按 `build_presales_evidence_book` → `build_customer_decision_context` → `build_problem_solution_fit` → `build_reading_deck_blueprint` 顺序发布，每步用当前expectedRevision和当前上游ref。不要用 `repair_reading_deck_blueprint` 绕过上游失效，不创建虚假的 change-set 来保留旧审核。
- [ ] 逐步核对第6节失效边界，并保留断点回执。任何失败停在当前正式状态，修复和续接只能使用现有业务服务；不手写旧heads、state、签名、approved或confirmation-consumption。
- [ ] 对新source version执行两内容硬门与内容接纳，以真实独立审查结果填写语义检查；打开正式内容ReviewSession，由用户对当前版本保存三页决定/提交Batch，再取得当前版本可信G0回执。原Batch/G0保留历史，不能直接复制或替换它们的source version。
- [ ] 新G0建立后，才按既有Image-led流程检查scope/授权承接、policy、原子与逐页包。S06的页级文字finding可派生精确文字对象原子，不发送跨越禁用对象的整页原子；允许图33/36保留，禁用图39及同字节别名继续拒绝。

这不是重复索取材料或生图许可；新内容版本的审核/G0与持续材料授权是不同证据。如果希望等值迁移自动继承旧G0，须先正式设计可信迁移合同，本方案没有该能力，也不顺带实现。

## 6. 分阶段失效与恢复检查点

| 正式动作 | Gate及heads应有行为 | 失败后边界 |
|---|---|---|
| Plugin安装/配置/只读预检 | 客户state不变；不写业务版本 | 可恢复已核定旧插件/配置；不回滚客户历史 |
| finding登记 | 新事件/派生制品与revision；所有业务heads/Gate保留 | 保留有效finding，先对账再续接；不重登材料 |
| 发布Evidence/Context/Fit | 立即G0=open，G1–G4=locked；清除当前项之后主链heads（当前没有change-set） | 旧审核heads可能暂存，但不能证明新版本通过；禁止继续生图 |
| 发布新Blueprint | 清除主链之外content/*、review/session/*、agent/*、visual/*、delivery/*、chat-delivery/*及G0/G3/G4 confirmation等下游heads；Mission/materials保持 | 不强行恢复旧heads；不可变旧制品仍为历史 |
| 新硬门/接纳/Review/Batch/G0 | 由真实当前source version正式回执建立 | 假确认、旧challenge或旧Batch不得补齐新Gate |

源码依据是 `presales_content_service.py::_commit` 与 `_replacement_removals`、`GateEvaluator.content_source_replaced`、`MaterialFindingService.register`。已有 `kernel/confirmation-consumptions` 历史不能删除；实际清理集合按源码和该时刻heads核定。

对于本轮核对的r19、无change-set状态，Evidence发布移除`content/decision-context`、`content/problem-solution-fit`、`content/reading-blueprint`；顺序重建Context/Fit时这三个旧head已经不存在，不重复计作新删除。Blueprint发布将移除以下当前九个head：

- `content/acceptance`
- `content/gate/evidence`
- `content/gate/presales-reading`
- `content/review-batch`
- `content/review/decision/C2-S04`
- `content/review/decision/C2-S05`
- `content/review/decision/C2-S06`
- `gate/G0/confirmation`
- `review/session/content-full-deck`

整个过程保留`materials`、`mission/draft`、`mission/confirmation`、`project/manifest`、`release/target-policy`，以及已消耗确认的`kernel/confirmation-consumptions`历史。后者只能由新的真实确认正式追加，不能复制旧签名或清空它。所有旧不可变制品保留为历史，后续新出现的head仍需按正式源码规则核对。

两硬门通过后的接纳会令G0进入`locked`；当前ReviewSession、三页决定和Batch满足后，通过正式open进入`user-reviewable`，最后真实可信确认使G0=`passed`、G1=`open`。不是发布Blueprint后直接从`open`跳到`passed`。详细逐事务模型见审计`future_migration.steps`；建模的19次新事务只是流程核对，真实宿主打开/回执等可能增加事务，禁止预填最终revision。

正式迁移不是一个全链原子事务，因此必须按检查点记录，不能把失败时覆盖state恢复r19当作回滚方案。

## 7. 后续真实生图与原生验收边界

L2/M2通过仍不自动运行图片生成。总控安排真实请求时须绑定新当前G0、有效输入包、已有真实scope/授权承接，按新的明确设计请求使用 `generationIntent=new` 和新 `generationRequestId`；unknown只恢复原ID，不重发。已有材料、用途、接收方/模型、共同规范范围内授权持续有效，不因普通revision变化反复弹授权。

三页仍由 Image 2 决定正文构图；定版后原生环节沿唯一 TargetBinding 和完整区域映射忠实转换，内容、还原、编辑性、跨页一致和真实PowerPoint分开核验。此加载/迁移方案没有建立真实生图、用户定版、原生制品、PowerPoint或G3，不启动C3整套扩展。

## 8. 本方案的审查与交付

- [ ] 独立核对源码/包身份、真实宿主观察及其限制、6 finding来源等值、两阶段G0失效、检查点恢复、可执行正式入口与缺口处理。
- [ ] 方案通过后固定本文、只读证据和Review hash；同步唯一台账，回传总控，等待其受控实施安排。
- [ ] 本轮结束再次核对客户state字节/mtime、源码相对基准无变化、继承未跟踪文件及共享依赖链接保持。只新增方案/证据/台账，不使用全量历史测试结果冒称本轮新执行测试。
