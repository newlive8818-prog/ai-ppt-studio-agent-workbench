"""Machine-readable command line interface for the Skill runtime."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from .artifact_store import ArtifactStore
from .config import RuntimeConfig
from .errors import (
    AiPptError,
    ArtifactValidationError,
    ConfigurationError,
    ExperienceValidationError,
    InvalidTransitionError,
    MaterialImportError,
    ProjectNotFoundError,
    ProtectedPathError,
)
from .experience_models import ExperienceLevel
from .experience_store import ExperienceStore
from .materials import ImportMode, MaterialIntake
from .models import ArtifactKind, Gate
from .paths import PathPolicy
from .project_store import ProjectStore
from .review_html import ReviewHtml, ReviewKind
from .state_store import StateStore


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
    initialize.add_argument("--source-context", type=Path)

    intake = commands.add_parser("import")
    intake.add_argument("--project", type=Path, required=True)
    inputs = intake.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--source", type=Path)
    inputs.add_argument("--url")
    inputs.add_argument("--text")
    intake.add_argument("--label", default="用户输入")
    intake.add_argument(
        "--mode",
        choices=[mode.value for mode in ImportMode],
        default=ImportMode.COPY.value,
    )

    status = commands.add_parser("status")
    status.add_argument("--project", type=Path, required=True)

    pass_gate = commands.add_parser("pass-gate")
    pass_gate.add_argument("--project", type=Path, required=True)
    pass_gate.add_argument("--gate", choices=[gate.value for gate in Gate], required=True)
    pass_gate.add_argument("--evidence", action="append", required=True)

    reopen = commands.add_parser("reopen-gate")
    reopen.add_argument("--project", type=Path, required=True)
    reopen.add_argument("--gate", choices=[gate.value for gate in Gate], required=True)
    reopen.add_argument("--reason", required=True)

    save_artifact = commands.add_parser("save-artifact")
    save_artifact.add_argument("--project", type=Path, required=True)
    save_artifact.add_argument(
        "--kind", choices=[kind.value for kind in ArtifactKind], required=True
    )
    save_artifact.add_argument("--input", type=Path, required=True)

    show_artifact = commands.add_parser("show-artifact")
    show_artifact.add_argument("--project", type=Path, required=True)
    show_artifact.add_argument(
        "--kind", choices=[kind.value for kind in ArtifactKind], required=True
    )

    list_artifacts = commands.add_parser("list-artifacts")
    list_artifacts.add_argument("--project", type=Path, required=True)

    review = commands.add_parser("review")
    review.add_argument("--project", type=Path, required=True)
    review.add_argument(
        "--kind", choices=[kind.value for kind in ReviewKind], required=True
    )

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
        environment_profile = os.environ.get("AI_PPT_WORKSPACE_CONFIG")
        profile = (
            Path(environment_profile)
            if environment_profile
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


def dispatch(args: argparse.Namespace) -> dict[str, object]:
    config = build_config(args)
    policy = PathPolicy(config)
    projects = ProjectStore(config, policy)
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
            "capability_evidence": {
                "experience_evolution": experience_status,
            },
        }
    if command == "init":
        manifest = projects.create(args.name, source_context=args.source_context)
        state = StateStore(Path(manifest.project_root), policy).initialize()
        return {
            "ok": True,
            "command": command,
            "project": manifest.as_dict(),
            "state": state.as_dict(),
        }
    if command == "import":
        manifest = projects.load(args.project)
        intake = MaterialIntake(policy)
        project_root = Path(manifest.project_root)
        if args.source is not None:
            records = intake.add_local(
                project_root, args.source, ImportMode(args.mode)
            )
        elif args.url is not None:
            records = (intake.add_url(project_root, args.url),)
        else:
            records = (intake.add_text(project_root, args.text, args.label),)
        return {
            "ok": True,
            "command": command,
            "materials": [record.as_dict() for record in records],
        }
    if command == "status":
        manifest = projects.load(args.project)
        state = StateStore(Path(manifest.project_root), policy).load()
        return {
            "ok": True,
            "command": command,
            "project": manifest.as_dict(),
            "state": state.as_dict(),
        }
    if command == "pass-gate":
        manifest = projects.load(args.project)
        state = StateStore(Path(manifest.project_root), policy).pass_gate(
            Gate(args.gate), tuple(args.evidence)
        )
        return {"ok": True, "command": command, "state": state.as_dict()}
    if command == "reopen-gate":
        manifest = projects.load(args.project)
        state = StateStore(Path(manifest.project_root), policy).reopen_from(
            Gate(args.gate), args.reason
        )
        return {"ok": True, "command": command, "state": state.as_dict()}
    if command == "save-artifact":
        manifest = projects.load(args.project)
        input_path = policy.assert_source_readable(args.input)
        if not input_path.is_file():
            raise ArtifactValidationError(
                f"Artifact input must be a JSON file: {input_path}"
            )
        try:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactValidationError(
                f"Artifact input is not valid JSON: {input_path}"
            ) from exc
        if not isinstance(payload, dict):
            raise ArtifactValidationError("Artifact input must contain a JSON object")
        artifact = ArtifactStore(
            Path(manifest.project_root), policy
        ).save(ArtifactKind(args.kind), payload)
        return {
            "ok": True,
            "command": command,
            "artifact": artifact.as_dict(),
        }
    if command == "show-artifact":
        manifest = projects.load(args.project)
        artifact = ArtifactStore(
            Path(manifest.project_root), policy
        ).latest(ArtifactKind(args.kind))
        return {
            "ok": True,
            "command": command,
            "artifact": artifact.as_dict(),
        }
    if command == "list-artifacts":
        manifest = projects.load(args.project)
        artifacts = ArtifactStore(
            Path(manifest.project_root), policy
        ).list_latest()
        return {
            "ok": True,
            "command": command,
            "artifacts": {
                kind: artifact.as_dict() for kind, artifact in artifacts.items()
            },
        }
    if command == "review":
        manifest = projects.load(args.project)
        review_path = ReviewHtml(
            Path(manifest.project_root), policy
        ).generate(ReviewKind(args.kind))
        return {
            "ok": True,
            "command": command,
            "review_path": str(review_path),
        }
    if command == "experience-create":
        manifest = projects.load(args.project)
        payload = _load_json_object(args.input, policy, "Experience input")
        experience = experiences.create_candidate(manifest, payload)
        return {
            "ok": True,
            "command": command,
            "experience": experience.as_dict(),
        }
    if command == "experience-list":
        level = ExperienceLevel(args.level) if args.level else None
        items = experiences.list(level)
        return {
            "ok": True,
            "command": command,
            "experiences": [item.as_dict() for item in items],
        }
    if command == "experience-show":
        experience = experiences.get(args.experience)
        return {
            "ok": True,
            "command": command,
            "experience": experience.as_dict(),
        }
    if command == "experience-recommend":
        payload = _load_json_object(args.input, policy, "Experience context")
        recommendations = experiences.recommend(payload, limit=args.limit)
        return {
            "ok": True,
            "command": command,
            "recommendations": recommendations,
        }
    if command == "experience-apply":
        manifest = projects.load(args.project)
        payload = _load_json_object(args.input, policy, "Experience context")
        application = experiences.record_application(
            manifest, args.experience, payload
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
            ArtifactValidationError,
            ExperienceValidationError,
        ),
    ):
        return 4
    if isinstance(error, InvalidTransitionError):
        return 5
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
            {
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            },
            sys.stderr,
        )
        return code
    except Exception as exc:  # pragma: no cover - last-resort structured boundary
        _print_json(
            {
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            },
            sys.stderr,
        )
        return 10
