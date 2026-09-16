# C2 定版前原图修订反馈最小合同

状态：同一C2持续制作与必要修复授权内的实施细化，待源码、独审及真实样本验证；不增加用户Gate。依据总控2a66四基线v2.17§1.9，提交`1b7236f`及用户后续明确的排除前置/共同规范补充。28a9不复制或修改平行四基线。诊断包`decode62813b48`已独立交付，本切片不回改该封存包。

## 1. 内部诊断对象与独立核对

新增`artifact_type=image-led-content-diagnostic`、`diagnostic_version=image-led-content-diagnostic/v1`，通过原`review-visual-engineering`任务及`visual-contract`结果事务登记。任务唯一target为确切completed generation response，reviewer_kind/role固定engineering/visual-engineering-reviewer；不得由生成任务提交，不要求先登记candidate或声称内容检查已通过。

提交闭合字段：`artifact_type, diagnostic_version, project_id, pack_ref, generation_response_ref, slide_id, page_order, image_sha256, image_size, reviewer_kind, reviewer_role, excluded_content_check, issues`。image_size是原图像素`[width,height]`，核对真实图片解码结果，不能使用显示缩放尺寸。

`excluded_content_check`为`{result:passed|failed|not-established, detail:非空本地核对说明}`。它属于独立源图核对，不是新增用户确认；源码不能从生成链自动推断实图没有排除内容。只有通过该确切源图排除核对的诊断才能被编译为修订请求。即使来自已授权请求，已知包含39等排除内容的图也不能为删除这些内容而先外发。failed/not-established诊断可保留，但写前拒绝修订。

issues是1..128项的闭合union，原序保留：

- `missing-item`：`{kind,item_id}`，item_id必须是原pack的确切可见文案身份。
- `replace-item`：`{kind,item_id,bbox}`，替换文案只能从原item派生，没有replacement_text通道。
- `remove-extra-text`：`{kind,bbox,observed_text}`，observed_text为本地实际观察记录，不是事实源且不外发。传输payload中的该操作只保留kind与bbox；供应方公共投影可按下节从闭合操作派生固定中文动作，不接受自由指令字段。
- `common-rule`：`{kind,rule_key,bbox}`，rule_key仅为原common_rules的`typography_tokens,color_tokens,fallback_fonts,title_bar,background`之一。没有新颜色、字体、模板、列数或布局文字输入。

共同色彩按原规则实际含义核对：当前policy没有“排他色板”原文，正文辅助色、材料原色和无字装饰色不自动判为违规。标题栏的实际字体/配色差异可指向对应原规则；不能借修订扩大为清除全部辅助色的要求。

bbox为原图像素`[x,y,width,height]`，每项有限数值且非布尔，宽高正、边界位于实际图内；只定位差异，不规定输出坐标。同一文案不能同时missing/replace或重复，重复的同kind/bbox/规则操作拒绝。observed_text和排除detail限制为非空、至多2000字符，不把任何本地说明透传给供应方。结构校验只能证明引用/区域/类型合法，不能单独证明文字在像素中；实际视觉判断由对应独立任务承担。

服务端追加并绑定`reviewer_task_id, context_pack_ref, producer_task_id, source_payload_sha256, authorization_binding`，最后一项由当前policy/scope/grant和原生成链派生，不接受调用者自报。诊断头按原response hash分别存储，不要求源图是最新生成结果：S05v3与v4必须各自按真实response/hash解析，不按文件名或最近时间选图。后续对同一源图的新诊断会使旧诊断不再作为当前修订入口，但原记录仍保留。

## 2. 派生授权与原图核验

修订编译须在任何入队/外发之前逐项完成：

1. 解析本项目正式生成任务及其不可变ContextPack、原request slot的确切completed response，核对request/pack/payload hash和页身份；started、unknown、任意路径/调用者图片bytes均拒绝。
2. 完整解码原image_base64，核对原图SHA256、尺寸、PNG MIME和单帧性，不缩放裁切，也不把别的相似图当作目标。
3. 重新编译当前原pack及其semantic binding，沿check_policy/authorized_scope重验当前Blueprint/Evidence/G0、原文、共同规范、来源用途、排除、接收方/型号与有效grant。历史请求的原base payload必须逐项等于当前重新派生的base payload。
4. 核验该确切原图已由独立源图诊断判定excluded_content passed，并保留其任务/源图/当前诊断身份。原材料仍须通过已有排除机制；不能把派生规则当成任意旧grant放行。
5. 仅对同项目/同页/同原pack/同授权来源/同CRS与gpt-image-2生成链，按本已批准纠错用途派生edit-target资格，不修改旧scope/grant，不创建MaterialAtom或第二事实源。旧许可失效或来源变化时写前拒绝，不请求替代性“自动许可”。

归档诊断本身不确认候选、不改变G0、不形成用户接受差异。生成结果和诊断仍由Python唯一业务内核写入。

## 3. 独立修订输入与供应方编译

继续原`generate-slide-images`任务与new/recover语义，targetRefs唯一元素改为已登记诊断ref；普通pack目标保持旧行为。自由action.instructions只留任务内部，不外发。

新增显式`payload_version=image-led-image2-repair-input/v1`，闭合字段：`payload_version,receiver,model,base_payload,edit_target,issues`。base_payload为完整不变的原image-led-image2-input/v2；外层receiver/model与base严格相等，首版只支持已选CRS/gpt-image-2。edit_target闭合为`{role:edit-target,image_sha256,data_base64,mime_type:image/png,width,height}`，全部由上述源响应派生。传输payload的issues已去除observed_text；其余仍严格对应本地诊断和原item/规则身份。

外层运输协议为`image-led-image2-repair-transport/v1`；preflight使用原image-led-image2-preflight/v2的generation_protocol显式回报修订协议，旧wrapper不支持时入队前失败。原v1/v2数据结构不静默增加字段。

Image2编译从原v2可见内容/非可见语义/材料公共投影派生，保持全部原文与原顺序。edit target作为第1图片，原图片材料保持原字节、原顺序及原用途随后排列；所有公共image_number说明相应偏移，原text/material/item内部身份仍按原alias机制投影。原材料保留指输入与角色保留，不强迫可选材料全部上版。

固定系统修订要求明确：对第1张确切源图处理已列内容与共同规范差异；原图中的额外文字不成为新的指定文案，所有指定文案仍只来自base confirmed_visible_copy；差异坐标只用于定位问题，Image2可按修正需要自主构图并沿用原共同规范。没有自由style instructions，也不向新图写入字段名、bbox数值或内部说明。原通用生成分支的prompt保持不变。

2026-09-11 S05正式修订后的表达补强：仅在wrapper的修订公共投影中，将`repair_context`置于完整原输入说明之前，并给每个issue派生固定中文`instruction`。派生只使用已验证的kind、原item公共别名、既有rule_key和原bbox，不外发observed_text或自由action.instructions，不扩大上述传输输入字段。明确第1张源图实际宽高、左上原点、x向右/y向下、bbox顺序`[x,y,width,height]`；宽高不是右下端点、不按请求输出尺寸缩放。逐问题说明补回、替换、删除或原共同规则纠正；删除只针对该区域额外的这一次文字呈现，完整保留清单中合法原条目及同文不同项，不作全页禁词，也不能将额外文字移到别处或换标签继续保留。坐标与指令只用于定位修订，正文构图自主性保持。该补强来自真实失败的可读性诊断；不证明模型内部失败原因，也不预先声称新图会通过。

## 4. 返回、恢复与下游

每次修订使用新的显式请求ID，记录原pack和diagnostic/source response绑定与完整修订payload hash。传输沿已审stream和decode诊断，仅一次POST、TLS不变。unknown只表示请求结果不明；最多说“反馈随请求发出”，不能说模型已收到或执行，也不自动重发或回填旧结果。

新图完整解码与输出适用性必须按原base payload重验，不能因repair版本让现有fitness检查被跳过。新candidate仍由当前对应生成任务提交，并按原pack核验指定文案/材料和新response的精确图像。随后完整源图核对、AI工作选定及新的TargetBinding分别执行；不能因completed自动选定，不能继承旧图的区域映射或验收。Native renderer与定版后忠实转换标准保持。

## 5. 执行切片与验证

- 纯合同与provider：新增image_repair小模块、闭合输入/issue验证、精确edit target及原材料序号、修订preflight。先合成红测，再实现；旧两协议/两型号请求保持。
- Runtime与任务：独立诊断结果登记/校验、原生成链及排除检查、精确修订目标编译、context/request/response身份、历史recover、候选和fitness穿透。先反例和端到端合成链，再接入。
- 两份调用参考只描述新正式入口及必要判断；不增加用户界面/Gate。
- 对应旧新专项、独立代码审查、精确候选差分后交总控真实修订；不扩测无关项目模块，不做通用模型注册或修图平台。

最低拒绝：错项目/页/pack/response/hash/尺寸、unknown源图、过期依赖/grant/诊断、非独立排除检查或排除未通过、任意路径/图片/替换文案/free instructions、无效或重复item/规则/bbox、原材料遗漏或序号错位、旧wrapper不支持仍入队、修订unknown重发/历史改写、新图绕过完整核对或继承用户认可。
