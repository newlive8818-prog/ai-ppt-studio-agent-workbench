"""Machine-readable schema 3 command line interface for the Skill runtime."""

from __future__ import annotations

import argparse
import base64
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from ai_ppt_studio.application.project_service import (
    ProjectCommandService,
    ProjectService,
)
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import (
    AiPptError,
    ConfigurationError,
    ExperienceValidationError,
    MaterialImportError,
    ProjectNotFoundError,
    ProtectedPathError,
)
from ai_ppt_studio.experience_models import ExperienceLevel
from ai_ppt_studio.experience_store import ExperienceStore
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.paths import PathPolicy


class CliUsageError(ConfigurationError):
    """Raised instead of allowing argparse to print non-JSON errors."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliUsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="ai-ppt-studio")
    parser.add_argument("--workspace-config", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--source-repo-root", type=Path)
    parser.add_argument("--install-root", type=Path)
    parser.add_argument("--upstream-root", type=Path)
    parser.add_argument(
        "--extra-protected-root",
        "--protect",
        dest="extra_protected_root",
        type=Path,
        action="append",
        default=[],
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("preflight")

    initialize = commands.add_parser("init")
    initialize.add_argument("--name", required=True)
    initialize.add_argument("--project-id", default="")

    intake = commands.add_parser("import")
    intake.add_argument("--project", type=Path, required=True)
    inputs = intake.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--source", type=Path)
    inputs.add_argument("--url")
    inputs.add_argument("--text")
    intake.add_argument("--label", default="用户输入")
    intake.add_argument("--mode", choices=("copy",), default="copy")

    status = commands.add_parser("status")
    status.add_argument("--project", type=Path, required=True)

    experience_create = commands.add_parser("experience-create")
    experience_create.add_argument("--project", type=Path, required=True)
    experience_create.add_argument("--input", type=Path, required=True)

    experience_list = commands.add_parser("experience-list")
    experience_list.add_argument(
        "--level", choices=[level.value for level in ExperienceLevel]
    )

    experience_show = commands.add_parser("experience-show")
    experience_show.add_argument("--experience", required=True)

    experience_recommend = commands.add_parser("experience-recommend")
    experience_recommend.add_argument("--input", type=Path, required=True)
    experience_recommend.add_argument("--limit", type=int, default=5)

    experience_apply = commands.add_parser("experience-apply")
    experience_apply.add_argument("--project", type=Path, required=True)
    experience_apply.add_argument("--experience", required=True)
    experience_apply.add_argument("--input", type=Path, required=True)

    experience_evaluate = commands.add_parser("experience-evaluate")
    experience_evaluate.add_argument("--application", required=True)
    experience_evaluate.add_argument("--input", type=Path, required=True)

    experience_set_level = commands.add_parser("experience-set-level")
    experience_set_level.add_argument("--experience", required=True)
    experience_set_level.add_argument(
        "--level", choices=[level.value for level in ExperienceLevel], required=True
    )
    experience_set_level.add_argument("--reason", required=True)

    experience_rollback = commands.add_parser("experience-rollback")
    experience_rollback.add_argument("--experience", required=True)
    experience_rollback.add_argument("--version", type=int, required=True)
    experience_rollback.add_argument("--reason", required=True)
    return parser


def build_config(args: argparse.Namespace) -> RuntimeConfig:
    explicit = (
        args.runtime_root,
        args.source_repo_root,
        args.install_root,
        args.upstream_root,
    )
    if any(value is not None for value in explicit):
        if not all(value is not None for value in explicit):
            raise ConfigurationError(
                "Explicit configuration requires all four root arguments"
            )
        return RuntimeConfig.create(
            runtime_root=args.runtime_root,
            source_repo_root=args.source_repo_root,
            install_root=args.install_root,
            upstream_root=args.upstream_root,
            extra_protected_roots=tuple(args.extra_protected_root),
        )
    profile = args.workspace_config
    if profile is None:
        configured = os.environ.get("AI_PPT_WORKSPACE_CONFIG")
        profile = (
            Path(configured)
            if configured
            else Path.home() / "Documents" / "AI-PPT-Workspace" / "workspace.json"
        )
    config = RuntimeConfig.from_workspace_file(profile)
    if not args.extra_protected_root:
        return config
    return RuntimeConfig.create(
        runtime_root=config.runtime_root,
        source_repo_root=config.source_repo_root,
        install_root=config.install_root,
        upstream_root=config.upstream_root,
        extra_protected_roots=(
            *config.protected_roots,
            *tuple(args.extra_protected_root),
        ),
    )


def _project_kernel(projects: ProjectService, project: Path) -> ProjectKernel:
    root = projects.resolve_project(project)
    try:
        payload = json.loads(
            (root / "kernel" / "state.json").read_text(encoding="utf-8")
        )
        project_id = str(payload["project_id"])
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise ProjectNotFoundError(f"Schema 3 project state is invalid: {root}") from exc
    return ProjectKernel(root, project_id=project_id)


def _project_payload(kernel: ProjectKernel, name: str) -> dict[str, object]:
    state = kernel.load()
    return {
        "project_id": state.project_id,
        "name": name,
        "project_root": str(kernel.project_root),
        "schema_version": state.schema_version,
        "revision": state.revision,
    }


def _add_materials(
    args: argparse.Namespace,
    policy: PathPolicy,
    kernel: ProjectKernel,
) -> list[dict[str, object]]:
    service = ProjectCommandService(kernel)
    revision = kernel.load().revision
    requests: list[dict[str, str]] = []
    if args.source is not None:
        source = policy.assert_source_readable(args.source)
        candidates = [source] if source.is_file() else sorted(source.rglob("*"))
        for candidate in candidates:
            if candidate.is_symlink():
                raise MaterialImportError(
                    f"Source directory contains a symlink: {candidate}"
                )
            if candidate.is_file():
                requests.append(
                    {
                        "material_type": "bytes",
                        "data_base64": base64.b64encode(candidate.read_bytes()).decode(
                            "ascii"
                        ),
                        "filename": candidate.name,
                        "mime_type": "application/octet-stream",
                        "label": candidate.name,
                        "value": "",
                    }
                )
    elif args.url is not None:
        requests.append(
            {
                "material_type": "url",
                "value": args.url,
                "data_base64": "",
                "filename": "",
                "mime_type": "text/uri-list",
                "label": args.label,
            }
        )
    else:
        requests.append(
            {
                "material_type": "text",
                "value": args.text,
                "data_base64": "",
                "filename": "",
                "mime_type": "text/plain",
                "label": args.label,
            }
        )
    if not requests:
        raise MaterialImportError("Source directory does not contain readable files")
    committed: list[dict[str, object]] = []
    for index, request in enumerate(requests):
        reference, state = service.add_material(
            f"cli:import:{revision}:{index}",
            revision,
            **request,
        )
        revision = state.revision
        committed.append({"artifact_ref": reference, "revision": revision})
    return committed


def dispatch(args: argparse.Namespace) -> dict[str, object]:
    config = build_config(args)
    policy = PathPolicy(config)
    projects = ProjectService(config)
    experiences = ExperienceStore(config, policy)
    command = args.command
    if command == "preflight":
        probe = policy.assert_write_allowed(config.runtime_root / "projects" / ".probe")
        experience_status = experiences.capability_status()
        return {
            "ok": True,
            "command": command,
            "roots": config.as_dict(),
            "python": platform.python_version(),
            "write_policy": {"ok": True, "probe": str(probe)},
            "runtime_contract": {
                "project_schema": "3.0",
                "artifact_reference": "artifact://<kind>/<sha256>",
                "managed_projects": len(projects.list_projects()),
            },
            "capabilities": {
                "runtime_foundation": True,
                "content_blueprint": True,
                "visual_conception": True,
                "image2": True,
                "presentations": True,
                "ppt_compilation": True,
                "delivery_validation": True,
                "experience_evolution": bool(experience_status["ready"]),
            },
            "capability_evidence": {"experience_evolution": experience_status},
        }
    if command == "init":
        kernel = projects.create_project(args.name, project_id=args.project_id)
        return {
            "ok": True,
            "command": command,
            "project": _project_payload(kernel, args.name.strip()),
        }
    if command == "import":
        kernel = _project_kernel(projects, args.project)
        return {
            "ok": True,
            "command": command,
            "materials": _add_materials(args, policy, kernel),
            "snapshot": dispatch_v16(
                {
                    "operation": "get-project-snapshot",
                    "project_root": str(kernel.project_root),
                }
            )["snapshot"],
        }
    if command == "status":
        kernel = _project_kernel(projects, args.project)
        result = dispatch_v16(
            {
                "operation": "get-project-snapshot",
                "project_root": str(kernel.project_root),
            }
        )
        return {**result, "command": command}
    if command == "experience-create":
        kernel = _project_kernel(projects, args.project)
        payload = _load_json_object(args.input, policy, "Experience input")
        experience = experiences.create_candidate(kernel, payload)
        return {
            "ok": True,
            "command": command,
            "experience": experience.as_dict(),
        }
    if command == "experience-list":
        level = ExperienceLevel(args.level) if args.level else None
        return {
            "ok": True,
            "command": command,
            "experiences": [item.as_dict() for item in experiences.list(level)],
        }
    if command == "experience-show":
        return {
            "ok": True,
            "command": command,
            "experience": experiences.get(args.experience).as_dict(),
        }
    if command == "experience-recommend":
        payload = _load_json_object(args.input, policy, "Experience context")
        return {
            "ok": True,
            "command": command,
            "recommendations": experiences.recommend(payload, limit=args.limit),
        }
    if command == "experience-apply":
        kernel = _project_kernel(projects, args.project)
        payload = _load_json_object(args.input, policy, "Experience context")
        application = experiences.record_application(
            kernel, args.experience, payload
        )
        return {
            "ok": True,
            "command": command,
            "application": application.as_dict(),
            "experience": experiences.get(args.experience).as_dict(),
        }
    if command == "experience-evaluate":
        payload = _load_json_object(args.input, policy, "Experience evaluation")
        evaluation = experiences.evaluate(args.application, payload)
        return {
            "ok": True,
            "command": command,
            "evaluation": evaluation.as_dict(),
            "experience": experiences.get(evaluation.experience_id).as_dict(),
        }
    if command == "experience-set-level":
        experience = experiences.set_level(
            args.experience, ExperienceLevel(args.level), args.reason
        )
        return {
            "ok": True,
            "command": command,
            "experience": experience.as_dict(),
        }
    if command == "experience-rollback":
        experience = experiences.rollback(
            args.experience, args.version, args.reason
        )
        return {
            "ok": True,
            "command": command,
            "experience": experience.as_dict(),
        }
    raise CliUsageError(f"Unsupported command: {command}")


def _load_json_object(path: Path, policy: PathPolicy, label: str) -> dict[str, object]:
    input_path = policy.assert_source_readable(path)
    if not input_path.is_file():
        raise ExperienceValidationError(f"{label} must be a JSON file: {input_path}")
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperienceValidationError(
            f"{label} is not valid JSON: {input_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ExperienceValidationError(f"{label} must contain a JSON object")
    return payload


def _print_json(payload: dict[str, Any], stream: Any) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    stream.flush()


def _exit_code(error: Exception) -> int:
    if isinstance(error, ProtectedPathError):
        return 3
    if isinstance(
        error,
        (
            ProjectNotFoundError,
            MaterialImportError,
            ExperienceValidationError,
        ),
    ):
        return 4
    if isinstance(error, ConfigurationError):
        return 2
    return 10


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        _print_json(dispatch(args), sys.stdout)
        return 0
    except (AiPptError, OSError, ValueError) as exc:
        code = _exit_code(exc)
        _print_json(
            {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}},
            sys.stderr,
        )
        return code
    except Exception as exc:  # pragma: no cover - last-resort structured boundary
        _print_json(
            {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}},
            sys.stderr,
        )
        return 10
