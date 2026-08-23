# AI PPT Studio v2.2 Authoritative ReviewSession Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改动已验收内容/视觉页面设计、不迁移旧内容生产链的前提下，把内容全稿审核与视觉专业审核共同依赖的 `ReviewSession`、真实宿主/AI 回执和四状态投影建立为 Python Runtime 权威事实。

**Architecture:** Python Runtime 通过不可变 artifact 和 `artifact_heads` 维护每种审核类型唯一的 current session；Node 只传输命令和真实回执，不拼接业务状态。审核对象 identity 由 `project_id + review_type + target_artifact_ref + source_version + revision` 决定；同 identity 重开零写恢复，不同 identity 在一个事务中 supersede 旧会话并创建新会话。四状态投影只读取权威 AgentTask 与 ReviewSession，不从 Widget 定时器、Browser 本地状态或 Node 临时 loopback session 推断。

**Tech Stack:** Python 3.12、`unittest`、schema 3 `ProjectKernel`/`ArtifactRepository`、Node MCP JSON bridge（本切片只接 Python operation，不做 Task 4 的工具目录重构）。

---

## 执行边界与当前事实

- 权威总计划：`产品代码/docs/superpowers/plans/2026-08-14-v22-unified-development-and-simplification.md`，本文件只校准并细化其中 Task 3，不建立第二套 v2.2 总计划。
- 当前已跟踪工作树在计划编写时干净，基点为 `267d964dfd89feb2dd9b4536ecc013e4dfdf2e49`；执行前必须重新核对，不能把该哈希当成永久事实。
- 当前 `产品代码/mcp/server.mjs` 的 `createAuthoritativeReviewSession()` 实际创建的是 Node 短时 loopback transport session，并且只接受视觉审核；它不是本计划定义的 Python 权威业务会话。
- 本切片不删除 `get-content-sidebar-review-projection`、五空间、旧内容角色或旧内容写链；这些属于总计划 Task 5–8 和 Task 14。
- 本切片不创建 `tool-catalog.mjs` 或 `ToolContractMap`；这些属于总计划 Task 4。
- 本切片不改变内容审核页和视觉审核页的布局、字段或交互设计，只为后续两张正式页面提供统一会话事实。
- 不修改真实 PPT 运行目录 `/Users/defei/Documents/AI-PPT-Workspace`；全部测试使用 `TemporaryDirectory`。
- `saved != host opened != host notified != AI received`；没有真实凭据时不能写入 `opened`、`sent` 或 `received`。

## 文件职责

- Create `产品代码/src/ai_ppt_studio/domains/review/__init__.py`：导出 ReviewSession 合同类型和 validator。
- Create `产品代码/src/ai_ppt_studio/domains/review/contracts.py`：字段枚举、identity、合法状态和 receipt 校验；不访问文件系统。
- Create `产品代码/src/ai_ppt_studio/application/review_session_service.py`：唯一 current session、恢复、supersede、提交和真实回执写入。
- Create `产品代码/src/ai_ppt_studio/application/project_status_projection.py`：从权威 current AgentTask/ReviewSession 投影唯一用户状态。
- Modify `产品代码/src/ai_ppt_studio/application/v16_bridge.py`：增加五个迁移期 operation；保留现有 dispatcher，Task 4 再注册为声明式工具目录。
- Create `产品代码/tests/test_v22_review_session.py`：合同、唯一性、恢复、并发修订、回执事实隔离和事务回滚。
- Create `产品代码/tests/test_v22_project_status_projection.py`：四状态和优先级。
- Modify `产品代码/tests/test_v16_bridge.py`：验证 JSON bridge 参数映射、拒绝前端伪造状态并返回 authoritative revision。

`产品代码/src/ai_ppt_studio/kernel/state.py` 本切片不预改：现有 `artifact_heads` 足以表达 current/by-id 两层索引。只有 RED 测试证明无法原子实现唯一性时，才允许另开小步骤修改 state schema；不得为了对应旧计划中的候选文件清单而制造冗余字段。

### Task 1: 建立纯领域 ReviewSession 合同

**Files:**
- Create: `产品代码/src/ai_ppt_studio/domains/review/__init__.py`
- Create: `产品代码/src/ai_ppt_studio/domains/review/contracts.py`
- Test: `产品代码/tests/test_v22_review_session.py`

- [ ] **Step 1: 写最小合法 payload、枚举和 identity 的失败测试**

在 `产品代码/tests/test_v22_review_session.py` 建立 `ReviewSessionContractTests`，测试数据必须使用固定时间，不依赖系统时钟：

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.review.contracts import (
    review_session_identity,
    validate_review_session,
)
from ai_ppt_studio.errors import ContractValidationError


def valid_session() -> dict[str, object]:
    return {
        "review_session_id": "content-session-01",
        "review_type": "content-full-deck",
        "project_id": "project-01",
        "target_artifact_ref": "artifact://reading-deck-blueprint/" + "a" * 64,
        "source_version": "content-v3",
        "revision": 17,
        "status": "ready",
        "open_policy": "notify-only",
        "host_open_status": "not-requested",
        "persistence_status": "saved",
        "host_notification_status": "pending",
        "ai_receipt_status": "pending",
        "created_at": "2026-08-23T00:00:00+00:00",
        "last_opened_at": None,
        "submitted_at": None,
    }


class ReviewSessionContractTests(unittest.TestCase):
    def test_valid_session_round_trips_and_identity_is_stable(self) -> None:
        payload = valid_session()
        self.assertEqual(validate_review_session(payload), payload)
        self.assertEqual(
            review_session_identity(payload),
            (
                "project-01",
                "content-full-deck",
                payload["target_artifact_ref"],
                "content-v3",
                17,
            ),
        )

    def test_rejects_invalid_review_type_status_and_future_revision(self) -> None:
        for field, value in (
            ("review_type", "content-evidence"),
            ("status", "approved"),
            ("open_policy", "auto-open"),
            ("host_open_status", "assumed-open"),
            ("persistence_status", "received"),
            ("host_notification_status", "assumed-sent"),
            ("ai_receipt_status", "assumed-received"),
        ):
            with self.subTest(field=field):
                payload = valid_session()
                payload[field] = value
                with self.assertRaises(ContractValidationError):
                    validate_review_session(payload, current_revision=17)
        with self.assertRaises(ContractValidationError):
            validate_review_session(valid_session(), current_revision=16)

    def test_requires_target_source_and_timestamp_fields(self) -> None:
        for field in (
            "review_session_id",
            "target_artifact_ref",
            "source_version",
            "created_at",
        ):
            with self.subTest(field=field):
                payload = valid_session()
                payload[field] = ""
                with self.assertRaises(ContractValidationError):
                    validate_review_session(payload, current_revision=17)
```

- [ ] **Step 2: 运行合同测试并确认 RED**

Run:

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_review_session.ReviewSessionContractTests
```

Expected: `ERROR`，明确缺少 `ai_ppt_studio.domains.review.contracts`，不是既有测试失败。

- [ ] **Step 3: 实现枚举、严格字段校验和稳定 identity**

在 `contracts.py` 定义以下公开常量和函数；validator 返回新字典，不能把调用方对象留作可变权威状态：

```python
from __future__ import annotations

import copy
from typing import Any

from ai_ppt_studio.errors import ContractValidationError

REVIEW_TYPES = frozenset({"content-full-deck", "visual-professional"})
SESSION_STATUSES = frozenset(
    {"preparing", "ready", "opened", "submitted", "superseded", "expired"}
)
OPEN_POLICIES = frozenset({"foreground-if-waiting", "notify-only"})
HOST_OPEN_STATUSES = frozenset(
    {"not-requested", "pending", "opened", "failed", "unavailable"}
)
PERSISTENCE_STATUSES = frozenset({"saving", "saved", "failed"})
HOST_NOTIFICATION_STATUSES = frozenset(
    {"not-requested", "pending", "sent", "failed", "unavailable"}
)
AI_RECEIPT_STATUSES = frozenset(
    {"pending", "received", "rejected", "unverified"}
)


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ContractValidationError(f"ReviewSession {field} is required")
    return value


def _enum(payload: dict[str, Any], field: str, allowed: frozenset[str]) -> str:
    value = _required_text(payload, field)
    if value not in allowed:
        raise ContractValidationError(f"ReviewSession {field} is invalid")
    return value


def validate_review_session(
    payload: dict[str, Any], *, current_revision: int | None = None
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("ReviewSession must be an object")
    normalized = copy.deepcopy(payload)
    for field in (
        "review_session_id",
        "project_id",
        "target_artifact_ref",
        "source_version",
        "created_at",
    ):
        normalized[field] = _required_text(normalized, field)
    normalized["review_type"] = _enum(normalized, "review_type", REVIEW_TYPES)
    normalized["status"] = _enum(normalized, "status", SESSION_STATUSES)
    normalized["open_policy"] = _enum(normalized, "open_policy", OPEN_POLICIES)
    normalized["host_open_status"] = _enum(
        normalized, "host_open_status", HOST_OPEN_STATUSES
    )
    normalized["persistence_status"] = _enum(
        normalized, "persistence_status", PERSISTENCE_STATUSES
    )
    normalized["host_notification_status"] = _enum(
        normalized, "host_notification_status", HOST_NOTIFICATION_STATUSES
    )
    normalized["ai_receipt_status"] = _enum(
        normalized, "ai_receipt_status", AI_RECEIPT_STATUSES
    )
    revision = normalized.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ContractValidationError("ReviewSession revision must be a non-negative integer")
    if current_revision is not None and revision > current_revision:
        raise ContractValidationError("ReviewSession revision cannot be in the future")
    for field in ("last_opened_at", "submitted_at"):
        if normalized.get(field) is not None and not str(normalized[field]).strip():
            raise ContractValidationError(f"ReviewSession {field} is invalid")
    return normalized


def review_session_identity(payload: dict[str, Any]) -> tuple[str, str, str, str, int]:
    normalized = validate_review_session(payload)
    return (
        normalized["project_id"],
        normalized["review_type"],
        normalized["target_artifact_ref"],
        normalized["source_version"],
        normalized["revision"],
    )
```

`__init__.py` 只导出 `REVIEW_TYPES`、`review_session_identity` 和 `validate_review_session`，不放业务逻辑。

- [ ] **Step 4: 运行合同测试并确认 GREEN**

Run:

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_review_session.ReviewSessionContractTests
```

Expected: 输出包含 `Ran 3 tests` 和 `OK`。

- [ ] **Step 5: 提交领域合同**

```bash
git add 产品代码/src/ai_ppt_studio/domains/review/__init__.py 产品代码/src/ai_ppt_studio/domains/review/contracts.py 产品代码/tests/test_v22_review_session.py
git diff --cached --check
git commit -m "feat: define authoritative review session contract"
```

### Task 2: 实现唯一 current session、恢复、supersede 和真实回执

**Files:**
- Create: `产品代码/src/ai_ppt_studio/application/review_session_service.py`
- Modify: `产品代码/tests/test_v22_review_session.py`
- Test: `产品代码/tests/test_kernel_transactions.py`

- [ ] **Step 1: 写唯一性、零写恢复和原子 supersede 的失败测试**

测试 fixture 直接初始化临时 kernel，并先提交一个当前审核目标：

```python
import tempfile
from pathlib import Path

from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


def kernel_with_target(root: Path) -> tuple[ProjectKernel, str]:
    kernel = ProjectKernel.initialize(root, project_id="project-01")
    target = {"title": "完整内容审核", "slides": [{"slide_id": "s1"}]}
    state = kernel.commit(
        command_id="seed-target-v1",
        expected_revision=0,
        event_type="test.target-created",
        artifact_updates={
            "content/reading-deck-blueprint": ("reading-deck-blueprint", target)
        },
    )
    return kernel, state.artifact_heads["content/reading-deck-blueprint"]


class ReviewSessionServiceTests(unittest.TestCase):
    def test_same_identity_reopens_without_a_second_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, target_ref = kernel_with_target(Path(temp))
            service = ReviewSessionService(
                kernel, clock=lambda: "2026-08-23T00:00:00+00:00"
            )
            first, first_state = service.open_or_resume(
                command_id="open-1",
                expected_revision=1,
                review_type="content-full-deck",
                target_artifact_ref=target_ref,
                source_version="content-v1",
                target_revision=1,
                open_policy="foreground-if-waiting",
            )
            resumed, resumed_state = service.open_or_resume(
                command_id="open-2",
                expected_revision=first_state.revision,
                review_type="content-full-deck",
                target_artifact_ref=target_ref,
                source_version="content-v1",
                target_revision=1,
                open_policy="foreground-if-waiting",
            )
            self.assertEqual(resumed, first)
            self.assertEqual(resumed_state.revision, first_state.revision)
            self.assertEqual(len(tuple(kernel.events_root.iterdir())), 2)

    def test_new_identity_atomically_supersedes_old_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, first_ref = kernel_with_target(Path(temp))
            service = ReviewSessionService(kernel)
            first, state = service.open_or_resume(
                command_id="open-v1",
                expected_revision=1,
                review_type="content-full-deck",
                target_artifact_ref=first_ref,
                source_version="content-v1",
                target_revision=1,
                open_policy="notify-only",
            )
            state = kernel.commit(
                command_id="seed-target-v2",
                expected_revision=state.revision,
                event_type="test.target-updated",
                artifact_updates={
                    "content/reading-deck-blueprint": (
                        "reading-deck-blueprint",
                        {"title": "v2", "slides": [{"slide_id": "s1"}]},
                    )
                },
            )
            second_ref = state.artifact_heads["content/reading-deck-blueprint"]
            second, final = service.open_or_resume(
                command_id="open-v2",
                expected_revision=state.revision,
                review_type="content-full-deck",
                target_artifact_ref=second_ref,
                source_version="content-v2",
                target_revision=state.revision,
                open_policy="notify-only",
            )
            old = kernel.artifacts.resolve(
                ArtifactReference.parse(
                    final.artifact_heads[f"review/session/{first['review_session_id']}"]
                )
            )["payload"]
            self.assertEqual(old["status"], "superseded")
            self.assertNotEqual(second["review_session_id"], first["review_session_id"])
            self.assertEqual(
                final.artifact_heads["review/session/current/content-full-deck"],
                final.artifact_heads[f"review/session/{second['review_session_id']}"]
            )

    def test_read_only_evidence_never_creates_a_business_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, target_ref = kernel_with_target(Path(temp))
            with self.assertRaises(ContractValidationError):
                ReviewSessionService(kernel).open_or_resume(
                    command_id="open-evidence",
                    expected_revision=1,
                    review_type="content-evidence",
                    target_artifact_ref=target_ref,
                    source_version="content-v1",
                    target_revision=1,
                    open_policy="foreground-if-waiting",
                )
            self.assertFalse(
                any(slot.startswith("review/session/") for slot in kernel.load().artifact_heads)
            )
```

- [ ] **Step 2: 运行 service 测试并确认 RED**

Run:

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_review_session.ReviewSessionServiceTests
```

Expected: `ERROR`，缺少 `review_session_service`。

- [ ] **Step 3: 实现 current/by-id 双索引和确定性 session identity**

`ReviewSessionService` 必须提供六个公开方法，参数和返回值不得另造同义版本：

| 方法 | 关键字参数 | 返回值 |
|---|---|---|
| `open_or_resume` | `command_id: str, expected_revision: int, review_type: str, target_artifact_ref: str, source_version: str, target_revision: int, open_policy: str` | `tuple[dict[str, Any], KernelState]` |
| `record_host_open_receipt` | `command_id: str, expected_revision: int, review_session_id: str, result: str, receipt_ref: str` | `tuple[dict[str, Any], KernelState]` |
| `record_host_notification_receipt` | `command_id: str, expected_revision: int, review_session_id: str, result: str, receipt_ref: str` | `tuple[dict[str, Any], KernelState]` |
| `record_ai_receipt` | `command_id: str, expected_revision: int, review_session_id: str, result: str, receipt_ref: str` | `tuple[dict[str, Any], KernelState]` |
| `mark_submitted` | `command_id: str, expected_revision: int, review_session_id: str` | `tuple[dict[str, Any], KernelState]` |
| `supersede_current` | `command_id: str, expected_revision: int, review_type: str` | `tuple[dict[str, Any] | None, KernelState]` |

实现时用以下精确 slot 约定，不给 `KernelState` 增加第二份会话状态：

```python
CURRENT_SLOT = "review/session/current/{review_type}"
IDENTITY_SLOT = "review/session/{review_session_id}"
ARTIFACT_KIND = "review-session"
```

用 canonical JSON 的 SHA-256 前 24 位构造稳定 ID；不能用当前时间或 Node 端 UUID 决定业务 identity：

```python
def _session_id(identity: tuple[str, str, str, str, int]) -> str:
    encoded = json.dumps(
        identity, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return "review-session-" + hashlib.sha256(encoded).hexdigest()[:24]
```

`open_or_resume()` 的顺序必须是：加载 state → 如果 current identity 完全相同则零写返回 → 验证新目标 ref 可解析且仍是某个 current head → 要求 `target_revision == state.revision` → 构造新会话 → 若有旧 current，把旧 payload 改为 `superseded` → 在一次 `kernel.commit()` 中同时更新旧 by-id、新 by-id 和 current。新会话初始状态由 Runtime 固定：

```python
session = {
    "review_session_id": session_id,
    "review_type": review_type,
    "project_id": state.project_id,
    "target_artifact_ref": target_artifact_ref,
    "source_version": source_version,
    "revision": target_revision,
    "status": "ready",
    "open_policy": open_policy,
    "host_open_status": (
        "pending" if open_policy == "foreground-if-waiting" else "not-requested"
    ),
    "persistence_status": "saved",
    "host_notification_status": (
        "pending" if open_policy == "notify-only" else "not-requested"
    ),
    "ai_receipt_status": "pending",
    "created_at": self.clock(),
    "last_opened_at": None,
    "submitted_at": None,
}
```

- [ ] **Step 4: 写并实现三个相互独立的真实回执测试**

增加测试：保存 session 后只记录 host open，断言 notification/AI 状态不变化；只记录 notification，断言 AI 不变化；`received` 缺 `receipt_ref` 必须零写失败；提交不自动关闭 session。

```python
opened, state = service.record_host_open_receipt(
    command_id="host-open",
    expected_revision=state.revision,
    review_session_id=session["review_session_id"],
    result="opened",
    receipt_ref="host-receipt://open/001",
)
self.assertEqual(opened["host_open_status"], "opened")
self.assertEqual(opened["host_notification_status"], "not-requested")
self.assertEqual(opened["ai_receipt_status"], "pending")

before = kernel.load()
with self.assertRaises(ContractValidationError):
    service.record_ai_receipt(
        command_id="forged-ai-receipt",
        expected_revision=before.revision,
        review_session_id=session["review_session_id"],
        result="received",
        receipt_ref="",
    )
self.assertEqual(kernel.load(), before)
```

合法映射固定为：

- host open `opened | failed | unavailable` → 同名 `host_open_status`；`opened` 必须有非空 receipt。
- host notification `sent | failed | unavailable` → 同名 `host_notification_status`；`sent` 必须有非空 receipt。
- AI receipt `received | rejected | unverified` → 同名 `ai_receipt_status`；`received | rejected` 必须有非空 receipt。
- 每次更新同时写 current slot 与同一 session by-id slot，且先校验该 session 仍是 current；superseded session 不接受新反馈或回执。
- `mark_submitted()` 只写 `status=submitted` 和 `submitted_at`，不得改变打开、通知或 AI 回执状态。

- [ ] **Step 5: 运行 ReviewSession 与 kernel 原子性测试**

Run:

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_review_session tests.test_kernel_transactions
```

Expected: 全部 `OK`；revision conflict、state 写失败和 object/event 清理测试保持通过。

- [ ] **Step 6: 提交权威会话服务**

```bash
git add 产品代码/src/ai_ppt_studio/application/review_session_service.py 产品代码/tests/test_v22_review_session.py
git diff --cached --check
git commit -m "feat: persist authoritative review sessions"
```

### Task 3: 建立四种唯一用户状态投影

**Files:**
- Create: `产品代码/src/ai_ppt_studio/application/project_status_projection.py`
- Create: `产品代码/tests/test_v22_project_status_projection.py`

- [ ] **Step 1: 写优先级和 notify-only 例外的失败测试**

测试必须覆盖精确优先级：

```python
class ProjectStatusProjectionTests(unittest.TestCase):
    def test_blocked_task_has_highest_priority(self) -> None:
        projection = ProjectStatusProjectionService(kernel).project()
        self.assertEqual(projection["status"], "任务受阻")
        self.assertEqual(projection["object_type"], "runtime-task")
        self.assertEqual(projection["object_ref"], blocked_task_ref)

    def test_foreground_ready_review_requires_user(self) -> None:
        projection = ProjectStatusProjectionService(kernel).project()
        self.assertEqual(projection["status"], "需要你处理")
        self.assertEqual(projection["object_type"], "content-review")
        self.assertEqual(projection["next_action"], "打开或继续内容全稿审核")

    def test_notify_only_ready_review_is_available_without_focus_takeover(self) -> None:
        projection = ProjectStatusProjectionService(kernel).project()
        self.assertEqual(projection["status"], "成果已可查看")
        self.assertEqual(projection["next_action"], "需要时打开内容全稿审核")

    def test_queued_task_projects_ai_processing(self) -> None:
        projection = ProjectStatusProjectionService(kernel).project()
        self.assertEqual(projection["status"], "AI 正在处理")
        self.assertEqual(projection["object_type"], "runtime-task")
```

fixture 用 `kernel.commit()` 写 `agent/task/active` 和 ReviewSession heads；不得 mock `ProjectStatusProjectionService` 的内部选择逻辑。

- [ ] **Step 2: 运行状态测试并确认 RED**

Run:

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_project_status_projection
```

Expected: `ERROR`，缺少 `project_status_projection`。

- [ ] **Step 3: 实现只读投影和固定优先级**

公开 API 只有：

```python
class ProjectStatusProjectionService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def project(self) -> dict[str, Any]:
        state = self.kernel.load()
        candidates = self._candidates(state)
        if not candidates:
            return {
                "status": "AI 正在处理",
                "object_type": "runtime-task",
                "object_ref": f"project://{state.project_id}",
                "reason": "当前没有等待用户处理的审核或已确认阻断。",
                "next_action": "继续当前 Codex 任务",
                "revision": state.revision,
            }
        return min(candidates, key=lambda item: item[0])[1]
```

候选优先级常量固定为：

```python
PRIORITY = {
    "任务受阻": 0,
    "需要你处理": 1,
    "成果已可查看": 2,
    "AI 正在处理": 3,
}
```

映射规则：

- active task `failed | blocked` → `任务受阻`；reason 使用非空 `error`，没有错误文字时使用“运行任务未能继续”。
- current session `ready | opened` 且 `foreground-if-waiting` → `需要你处理`。
- current session `ready | opened` 且 `notify-only` → `成果已可查看`，不得提前投影为“需要你处理”。
- active task `queued | running` 或 submitted session 等待 AI receipt → `AI 正在处理`。
- `review_type=content-full-deck` 映射 `object_type=content-review`；`visual-professional` 映射 `visual-review`。
- 每个结果必须包含非空 `reason`、唯一 `next_action` 和当前 `state.revision`。

- [ ] **Step 4: 运行状态测试并确认 GREEN**

Run:

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_project_status_projection
```

Expected: 输出至少包含 `Ran 4 tests` 和 `OK`；若增加了边界用例，实际测试数可以更高。

- [ ] **Step 5: 提交状态投影**

```bash
git add 产品代码/src/ai_ppt_studio/application/project_status_projection.py 产品代码/tests/test_v22_project_status_projection.py
git diff --cached --check
git commit -m "feat: project authoritative user status"
```

### Task 4: 把 ReviewSession 和用户状态接入 Python bridge

**Files:**
- Modify: `产品代码/src/ai_ppt_studio/application/v16_bridge.py`
- Modify: `产品代码/tests/test_v16_bridge.py`
- Test: `产品代码/tests/test_v22_review_session.py`

- [ ] **Step 1: 写五个 operation 的失败测试**

先测试 `open-or-resume-review-session` 和 `get-project-user-status`，再测试三个 receipt operation。请求形状固定如下：

```python
opened = dispatch_v16({
    "operation": "open-or-resume-review-session",
    "project_root": str(project),
    "command_id": "bridge-open-content-review",
    "expected_revision": revision,
    "review_type": "content-full-deck",
    "target_artifact_ref": target_ref,
    "source_version": "content-v1",
    "target_revision": revision,
    "open_policy": "foreground-if-waiting",
})
self.assertEqual(opened["session"]["review_type"], "content-full-deck")
self.assertEqual(opened["snapshot_revision"], revision + 1)

status = dispatch_v16({
    "operation": "get-project-user-status",
    "project_root": str(project),
})
self.assertEqual(status["status"]["status"], "需要你处理")
```

三个 receipt operation 使用以下字段：

```text
record-review-host-open: review_session_id, result, receipt_ref
record-review-host-notification: review_session_id, result, receipt_ref
record-review-ai-receipt: review_session_id, result, receipt_ref
```

每个写 operation 都必须带 `command_id` 和 `expected_revision`，返回更新后的 `session` 与 `snapshot_revision`。

- [ ] **Step 2: 写前端伪造状态零写测试**

以下请求必须在调用 service 前被拒绝，且 state、events、objects 不变化：

```python
for forged_field, forged_value in (
    ("host_open_status", "opened"),
    ("host_notification_status", "sent"),
    ("ai_receipt_status", "received"),
    ("persistence_status", "saved"),
):
    request = dict(valid_open_request)
    request[forged_field] = forged_value
    with self.assertRaises(ContractValidationError):
        dispatch_v16(request)
```

- [ ] **Step 3: 运行 bridge 测试并确认 RED**

Run:

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v16_bridge.V16BridgeTests tests.test_v22_review_session
```

Expected: 新 operation 因未注册而失败；旧 bridge 测试不应新增失败。

- [ ] **Step 4: 添加 bridge 依赖和五个 operation**

在 `dispatch_v16()` 创建：

```python
review_sessions = ReviewSessionService(kernel)
status_projection = ProjectStatusProjectionService(kernel)
```

在任何旧 content/visual write 分支之前增加五个精确分支。`open-or-resume-review-session` 必须先拒绝以下键：

```python
for field in (
    "status",
    "host_open_status",
    "persistence_status",
    "host_notification_status",
    "ai_receipt_status",
    "created_at",
    "last_opened_at",
    "submitted_at",
):
    if field in request:
        raise ContractValidationError(
            f"{field} is Runtime-owned and cannot be supplied by the client"
        )
```

所有写分支用 `_command_id(operation, request)`，所有结果都从 service 返回的 `KernelState.revision` 获取 `snapshot_revision`；Node 或前端不得用 `expected_revision + 1` 猜测。

- [ ] **Step 5: 运行 bridge、会话、状态和事务专项测试**

Run:

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v16_bridge tests.test_v22_review_session tests.test_v22_project_status_projection tests.test_kernel_transactions
```

Expected: 全部 `OK`。

- [ ] **Step 6: 提交 bridge operation**

```bash
git add 产品代码/src/ai_ppt_studio/application/v16_bridge.py 产品代码/tests/test_v16_bridge.py
git diff --cached --check
git commit -m "feat: expose authoritative review session operations"
```

### Task 5: 全量回归、边界审计和切片收口

**Files:**
- Verify only: `产品代码/src/ai_ppt_studio/`
- Verify only: `产品代码/mcp/`
- Verify only: `产品代码/widget/`
- Verify only: `产品代码/tests/`

- [ ] **Step 1: 运行全部 Python 测试**

```bash
cd 产品代码
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest discover -s tests -p 'test_*.py'
```

Expected: 所有测试通过；记录实际数量，不复用计划编写前的 `354/354`。

- [ ] **Step 2: 运行 Node 和 Widget 回归**

```bash
cd 产品代码
npm run typecheck
node --test tests/*.test.mjs
```

Expected: typecheck 与 Node 测试全部通过。若 loopback 监听在沙箱中报 `EPERM`，必须在已授权可绑定 `127.0.0.1` 的相同 checkout 重跑；`EPERM` 既不是 PASS，也不是产品回归。

- [ ] **Step 3: 审计本切片没有越界实现后续 Task**

Run:

```bash
rg -n "content-evidence.*review/session|ReviewSession.*content-evidence" 产品代码/src 产品代码/tests
rg -n "host_open_status.*opened|host_notification_status.*sent|ai_receipt_status.*received" 产品代码/widget/src 产品代码/mcp
rg -n "get_content_sidebar_review_projection|CompactWorkspace|StableNavigation" 产品代码/widget/src 产品代码/mcp/server.mjs
```

Expected:

- 只读内容证据不创建业务 ReviewSession；
- Widget/Node 没有新增伪造 `opened/sent/received` 的代码；
- 旧 sidebar/五空间仍可能存在，因为 Task 14 尚未执行，不能在本切片顺手删除；
- 本切片完成不代表 Task 4–17、真实宿主打开、Browser 长文档性能、PowerPoint、发布或用户验收完成。

- [ ] **Step 4: 检查工作树和补丁质量**

```bash
git status --short --branch
git diff --check
git log --oneline -8
```

Expected: 仅保留用户原有无关未跟踪目录；本切片的已跟踪修改已由独立提交承载；无 whitespace error；不 amend、不 merge、不 push。

- [ ] **Step 5: 记录切片完成边界**

交付说明必须分别报告：

1. 已实现并提交：Python 权威 ReviewSession、四状态投影、bridge operations；
2. 已自动验证：实际 Python/Node/typecheck 数量与命令；
3. 尚未验证：真实宿主打开/通知/AI 回执、Browser 恢复、用户验收；
4. 尚未研发：Task 4 工具目录、Task 5–8 新内容主链和正式内容页、Task 9–11 独立视觉反馈合同、Task 12–13 经验系统、Task 14–16 简化与发布合同；
5. 下一依赖：执行总计划 Task 4，再进入 Task 5/6 内容主链；不得因为 Task 3 全绿宣称 v2.2 项目研发完成。
