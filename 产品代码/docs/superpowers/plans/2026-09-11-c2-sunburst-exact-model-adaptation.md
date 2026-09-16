# C2 Sunburst 精确型号适配最小计划（已核定实施）

总控已于2026-09-11核定本计划并授权在同一C2直接实施；授权范围仅为必要适配器、测试、配置/合同说明及唯一台账，不包括真实HTTP、客户事务、安装或重启。沿用同一 CHG-IL-C2、分支 `codex/image-led-native-anchors` 和现有主执行任务。当前文档 HEAD 为 `696b594049cbe61fa6f990681079303e283e73e2`，运行候选的生产源仍为 `edb12848bad7b34cb0eb05c6a9b79097cf86422b`。r46 截止的宿主、grant、policy、packs 及自动审批拒绝事实已单独提交；本计划不改写该历史。

目标：允许明确选用 `CRS / gpt-image-2.5-sunburst`，保持 `n=1 / size=2048x1152 / quality=high / output_format=png`，从正式 scope 到真实 HTTP 请求及结果接纳使用一致身份。旧 `gpt-image-2` 路径继续兼容。此次不支持 Flare、泛称 `image2.5`、前缀匹配、任意模型、任意 endpoint 或自动降级。

## 1. 已确认输入及证据边界

- 总控 2026-09-11 明确核定本轮型号为 `gpt-image-2.5-sunburst`，并保留既有尺寸/质量。
- [当前 CRS catalog](/private/tmp/c2-image25-adaptation-20260911/crs-image-model-catalog.json)记录 GET `/v1/models` HTTP 200 且列出 Sunburst；这只证明目录可见，不证明 generation/edit 可执行。本任务没有重查 CRS、执行 helper 或发送生成请求。
- [官方型号页](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst)列出图像生成和编辑能力；[官方生成指南](https://developers.openai.com/api/docs/guides/image-generation)说明可直接指定该型号并使用自定义尺寸。2048×1152 满足其尺寸倍数、边长、比例及像素数约束，high 是支持的质量选项。官方能力与 CRS 当前转发能力分别验证。
- 历史 Flare 1024/low 的 HTTP 200 不作为本次 Sunburst、2048×1152/high 或 edit 的证据。

## 2. 实际代码缺口及最小方案选择

源码根目录：`/Users/defei/Library/Application Support/Codex API Client/codex-home/worktrees/28a9/PPT-codex-app/产品代码`。下列路径均相对此源码根。

| 位置 | 现状 | 最小修订 |
| --- | --- | --- |
| `src/ai_ppt_studio/adapters/image2_crs.py:27` | `MODEL` 固定为 gpt-image-2 | 保留旧默认值，增加精确 Sunburst 常量及仅两值的受限选择 |
| 同文件 `compile_body`，约 77/86/150 行 | payload 校验及 JSON/multipart model 均写死 | 增加经核定的 model 关键字参数，先校验受限值及 payload 一致，再由该值写真实 body |
| 同文件 `generate/preflight/main`，约 198/229/233/249 行 | 回执/probe 固定旧模型，main 只接受空 argv 或 --preflight | 只新增精确 Sunburst argv 形式，由 main 解析一次并传递同一选择；请求、预检、回执不能各自猜模型 |
| `src/ai_ppt_studio/adapters/image2_command.py:63/164/173/192` | 已知 wrapper 只接受两项 argv，配置和 probe 模型固定旧值 | 严格匹配下述两种完整 argv，并核验 configured model、payload model、probe model、response model 全相同 |
| `application/image_led_service.py:136/157/221` | scope/policy receiver/model 已严格相等，payload 已由 policy 派生 | 复用现有逻辑，用负例验证；不为适配而放松授权或改成模型家族匹配 |

推荐 **A：两种精确 argv + 既有闭合预检**。现有 probe 回执已经包含 model，生成 payload/回执也包含 model，因此此次无需新增 transport、payload、scope 或 preflight 版本，不扩公共 MCP 工具或 schema。

只接受：

```text
旧模型: (当前 sys.executable 绝对路径, 当前包 image2_crs.py 绝对路径)
         configured/payload/model = gpt-image-2
新模型: (同一 Python, 同一 wrapper, --model, gpt-image-2.5-sunburst)
         configured/payload/model = gpt-image-2.5-sunburst
```

预检只在以上已识别命令后追加 `--preflight`。wrapper main 的允许形式是旧的 `[]`、`[--preflight]`，以及新的 `[--model, gpt-image-2.5-sunburst]`、`[--model, gpt-image-2.5-sunburst, --preflight]`；不使用宽松参数解析、命令字符串或 shell。空参数仍明确表示旧模型，不是新模型缺失时的自动回退。

`compile_body` 的默认关键字值继续为旧 MODEL，保留现有调用；新路径必须显式传入已由完整 argv 确认的 Sunburst。adapter 不允许“两项旧 argv + 新 configured model”，也不允许“四项新 argv + 旧 payload”。所有这些不匹配在入队/认证/HTTP 前拒绝。preflight v1/v2 和 transport v1/v2 的字段结构保持，既有版本检查不放松；对新型号也执行相应闭合 schema 校验。

备选 **B：新增包含 receiver/model 的 preflight/v3** 同样可建立身份，但会扩大协议与兼容面。此次只有一个新增精确型号，A 已能闭合身份，故不采用 B。单纯替换 MODEL 常量则会破坏旧路径，不能作为方案。

## 3. 两条 HTTP 路径及模型真实性

- 无图片输入：既有 `/v1/images/generations`，JSON body。
- 有图片输入：既有 `/v1/images/edits`，multipart；一图为 `image`，多图为 `image[]`。原始图片字节、MIME、顺序和用途保持。
- 两条路径都从同一个已核定 model 变量生成 `model`，保持同一尺寸/质量/格式，保持一次发送、禁止重定向和 wrapper 内重试、安全错误输出。
- S06 的两张图虽然是可选素材池，当前输入仍包含它们，wrapper 因而走多图 edits；不能为躲避 edit 不支持而删图、改用文字描述或偷偷切回 generations。Image 2.5 仍负责定版前的正文设计自主选择。
- wrapper 回执的 model 表示本地已核验并实际放入请求的目标，不冒称上游执行模型的独立证明。合成验证必须检查真实发送的 JSON/multipart model，保存非敏感字段摘要、请求/响应身份和图像 hash。若上游提供可信 model 标识，则额外核验，缺失时明确没有独立上游模型证明；不能仅依据本地回执标签声称真实使用 Sunburst。

## 4. 已授权实施与验证任务

1. **窄合同同步**：先更新供应方准备规格中的固定型号、exact argv 和预检规则，以及输入 v2 规格中的能力预检描述。同步四基线相关说明和仓库 Skill 的配置说明，明确“Image 2”是整页设计责任角色，实际 provider/model 由核定配置和授权身份决定；不改角色责任、G0、71 条内容、设计定版约束或 UI。
2. **RED → 最小修复 → GREEN**：只预计修改上述两个 adapter 生产文件。添加旧/新精确型号矩阵，覆盖真实 JSON 与解析后的 multipart body、stdout 回执、stat-only 子进程和身份不匹配写前拒绝。若实证发现必须修改其他生产文件，先说明具体缺口，不能扩大成通用模型路由器。
3. **正式 Runtime 回归**：通过现有默认 MCP→Python bridge 入口验证旧 scope/new model、旧 grant/new scope、policy/pack/config 不一致均零入队；排队后模型/依赖漂移写前拒绝；unknown 恢复不重发、已拒绝请求不凭文件重放。新模型正向测试仍完整携带 v2 selected copy、语义和材料身份，内容/G0 不变。
4. **固定源码独审、包与宿主**：适用专项通过后对固定实现运行一次完整 Python 和 `npm run quality`，完成独立审查。本轮离线包集成核验两文件及配置指导入包；固定源码交总控进行非客户真实组件试验，之后另行受审打包/升级与实际宿主身份核验。不能继续把旧 edb 包称为支持 2.5。
5. **合成在线能力验证**：仅由总控在受审源码上执行或另行明确下发；使用纯本地合法 v2 envelope 和非客户合成文本/图像驱动受审实际 wrapper，进行组件级真实供应方集成测试；不读客户、不创建虚构 grant 或接受记录，只证明真实 HTTP 形态和响应解码，不证明正式 Runtime 或客户通过。正式 Runtime 闭环由后续真实三页另行证明。源码实施授权不包含执行这些真实调用。

重点测试文件：

```text
tests/test_image2_crs_provider.py
tests/test_image2_preflight.py
tests/test_image_led_v2.py
tests/test_image_led_v2_runtime.py
tests/test_image_led_execution_entrypoint.py
tests/image2-provider-preflight.test.mjs
```

目标反例至少包括：未知/Flare/泛别名、额外 argv、相似 wrapper 路径、配置/payload/CLI/probe/回执任一模型不匹配、旧命令被新标签冒充、v2 降级、nonce 错误、超时/非零退出、无图片/一图/两图实际 body model 错误、返回后非法模型/数据、同请求 unknown 二次发送。预检对 helper/HTTP 的计数必须为 0；前置型号身份不匹配对排队/认证/发送的计数必须为 0。已收到的 HTTP 或 transport 回执不匹配按 §7 记录发送已发生，拒绝结果且不得重试。

专项命令从独立验证副本的源码根运行，沿用既有固定 Python/Node 与依赖环境：

```bash
python3 -m unittest discover -s tests -p 'test_image2_crs_provider.py'
python3 -m unittest discover -s tests -p 'test_image2_preflight.py'
python3 -m unittest discover -s tests -p 'test_image_led_v2*.py'
python3 -m unittest discover -s tests -p 'test_image_led_execution_entrypoint.py'
node --test tests/image2-provider-preflight.test.mjs
```

完整验证在新实现稳定后执行一次，不重跑旧 edb 全量以代替新版本验证。

## 5. 当前能力证明要求

| 证据 | 成功标准 | 不能替代的证明 |
| --- | --- | --- |
| catalog（已有） | 当前 CRS 目录含精确 Sunburst；保留时点/hash | 不证明当前账户能生成或编辑 |
| 离线/本地预检 | 两种 exact argv；新模型真实 wrapper stat-only；新旧 schema、body 和回执一致；全部反例写前拒绝 | 不证明 HTTP 或模型输出 |
| generations 合成实测 | 至少一次无图片真实调用；Sunburst/2048×1152/high/PNG/n=1；200、恰好一图、完整解码尺寸匹配、原请求与结果关联 | 不证明 edits |
| edits 单图合成实测（总控可选追加） | 若执行，使用单张合成图，实际 image multipart 字段与原字节匹配；同模型/参数并取得可解码结果 | 不证明多图 |
| edits 多图合成实测 | 至少一次两张可辨识合成图，实际 image[] 顺序/原字节匹配；验证两图确进入请求；同模型/参数并取得可解码结果 | 不证明真实客户视觉保真或素材均被模型采用 |
| 真实客户三页 | 以上适用能力通过、精确新型号身份链及客户端外发条件满足后，由总控正式执行 | 不由 catalog、合成样本、旧 Flare 200 或本地标签自动得出 |

当前客户必需的在线证明为无图 generations 与双图 edits 两种请求形态，均使用固定 2048×1152/high；单图先离线覆盖，总控可追加真实验证，不新增为当前客户用途门槛。若 CRS 只在其他尺寸/质量或部分入口成功，记录准确 CapabilityGap，不降为1024/low、不退回 gpt-image-2、不修改材料或定版标准。输入被实际发送与输出确实遵循输入是两类证据；单次生成成功也不能保证设计质量。

## 6. 客户输入和后续承接

r46 的 scope/grant/policy/packs 绑定旧 `gpt-image-2`，保留历史身份，不能改内部字段冒充 Sunburst。总控在实际用户型号选择与有效外发批准基础上，通过正式入口派生新 scope（沿用原 92 项范围/排除关系，只体现本次真实型号变化）、取得匹配新 scope 的正式 grant，再登记新 policy 和三页 packs。grant 是绑定 scope 的证据，pack 是绑定 policy 的输入；不要求这些对象增添重复 model 字段，沿现有引用链核对精确 model 即可。

内容蓝图、材料来源、G0、71 条原 ID/原文/原序、标题目标和共同设计规范保持。新请求使用新输入引用和新的稳定 request ID；旧 S04 记录没有入队，无需 recover。已有用户批准不按每页或每次调用重问；模型变化所需的精确记录及客户端审批承接由总控负责。本任务不制造 grant、不调用确认 UI、不重放被拒请求。

总控已明确授权本次源码实施与独立审查，不新建任务或Change。固定源码提交后交回总控做当前账户的非客户合成generation和双图edit验证，再受审打包/升级。单图multipart分支先以离线行为测试覆盖；如需另做真实单图调用，由总控按必要性安排，不把它设为当前0图/2图客户用途的额外前置门。

## 7. 本轮核定补充与执行检查

预检响应model不符在任务入队/外发之前拒绝；真实HTTP响应或transport回执model不符只能在响应到达后拒绝接纳，记录unknown/不可用并保持不重试，不能声称已经发出的HTTP未发生。上游若显式返回model必须匹配，未返回时只记录请求绑定的型号，不制造独立上游证明。

- [x] 最小失败复现并保存RED日志。
- [x] 两适配器精确型号与argv实现。
- [x] 相关Python/Node集成与适用完整回归。
- [x] 四基线窄说明、专项规格、Skill/正式配置说明同步。
- [x] 固定源码独立审查，关闭确定阻断项。
- [x] 唯一台账与精确源码提交交接清单准备；实际提交、提交后核验与交接以本轮回执为准。
