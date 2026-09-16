"""Read-only C0 document/Git/archive checks. No product imports or dependencies."""
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from urllib.parse import unquote

BASE = "d77854385b830d5796b6da2b86e3c44021095398"
BASELINES = ["00-唯一研发基线索引-v1.0.md", "01-产品需求基线-v1.0.md",
             "02-系统详细设计-v1.0.md", "03-UI设计与交互规范-v1.0.md"]
PLAN = "产品代码/docs/superpowers/plans/2026-09-07-image-led-visual-upgrade-program-plan.md"
ENTRY = "04-Image-led-C0-接管入口.md"
EVIDENCE = "产品代码/docs/validation/c0-image-led-freeze/"
ALLOWED = set(BASELINES + [PLAN, ENTRY] + [EVIDENCE + p for p in
              ["evidence-index.md", "evidence-snapshot.json", "verification-report.md", "verify_freeze.py"]])
AC_HASH = "0f942cdef6bf8b1e0a18693eec72a42fcab42b9a08f291c93fee9283b7f46a49"


def git(repo, *args):
    return subprocess.check_output(["git", "-c", "core.quotepath=false", *args], cwd=repo)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--commit", help="Full frozen candidate SHA; archive and inspect every tracked file")
    args = parser.parse_args()
    repo = Path(args.root).resolve()
    errors = []
    report = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "base": BASE, "source_repo": str(repo), "product_tests": "NotRun",
              "powerpoint": "NotRun", "AC08": "NotEstablished"}
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    target = args.commit or head
    if args.commit and not re.fullmatch(r"[0-9a-f]{40}", target):
        raise SystemExit("--commit requires exact 40-character SHA")
    if subprocess.run(["git", "merge-base", "--is-ancestor", BASE, target], cwd=repo).returncode:
        errors.append("B0 is not ancestor")
    root = repo
    if args.commit:
        root = Path(tempfile.mkdtemp(prefix="c0-freeze-readback-", dir="/private/tmp"))
        with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", "--format=tar", target))) as archive:
            archive.extractall(root, filter="data")
        count = 0
        for item in git(repo, "ls-tree", "-r", "-z", target).split(b"\0"):
            if not item:
                continue
            meta, name = item.split(b"\t", 1)
            mode, kind, oid = meta.split()
            p = root / name.decode()
            if kind != b"blob" or not p.is_file():
                errors.append("archive missing/unsupported tracked entry: " + name.decode())
                continue
            raw = p.read_bytes()
            actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if actual != oid.decode():
                errors.append("archive blob mismatch: " + name.decode())
            count += 1
        report.update(archive_root=str(root), archive_blob_count=count)
    changed = set(git(repo, "diff", "--name-only", BASE, *([target] if args.commit else [])).decode().splitlines())
    if not args.commit:
        changed.update(git(repo, "ls-files", "--others", "--exclude-standard").decode().splitlines())
    if changed != ALLOWED:
        errors.append({"whitelist_unexpected": sorted(changed - ALLOWED), "whitelist_missing": sorted(ALLOWED - changed)})
    check = subprocess.run(["git", "diff", "--check", BASE, *([target] if args.commit else [])], cwd=repo, capture_output=True, text=True)
    if check.returncode:
        errors.append(check.stdout + check.stderr)
    report.update(candidate=target, mode="committed-archive" if args.commit else "working-tree", changed_files=sorted(changed))
    links = 0
    prototypes = 0
    for name in sorted(ALLOWED):
        p = root / name
        if not p.is_file():
            errors.append("required file missing: " + name)
            continue
        if not name.endswith(".md"):
            continue
        text = p.read_text()
        for url in re.findall(r"\]\(([^)]+)\)", text):
            if re.match(r"[a-z]+://|#", url):
                continue
            path = unquote(url.strip("<>").split("#", 1)[0])
            if not path:
                continue
            links += 1
            prototypes += "/prototypes/" in path
            if not (p.parent / path).exists():
                errors.append("broken relative link: " + name + " -> " + path)
        if name in BASELINES:
            if "v2.10" not in text.splitlines()[0] or "2026-09-07" not in text:
                errors.append("baseline version/date drift: " + name)
            for token in ["G0 后、原生结构冻结前", "选稿仅为视觉参考", "C2 承接", "string token map", "G2/G3/G4"]:
                if token not in text:
                    errors.append("missing baseline invariant: " + name + " / " + token)
            if re.search(r"Image 2 只(?:可|能)?在原生结构冻结后", text):
                errors.append("old active Image 2 restriction: " + name)
    plan = (root / PLAN).read_text()
    ac = re.findall(r"- \[ \] IL\d\d-AC.*", plan)
    if len(ac) != 35 or digest("\n".join(ac).encode()) != AC_HASH:
        errors.append("C1-C4 original AC changed")
    for n in range(1, 9):
        if f"C0-AC{n:02d}" not in plan:
            errors.append("missing C0 AC")
    if "C0 → 总控验收冻结包 → 新总控读取包并回执 → C1 → C2 → C3 → C4" not in plan:
        errors.append("C0 sequence missing")
    # Validate claimed existing integration paths, including R4-only experiment inputs.
    path_checks = []
    responsibility = plan.split("## 8.", 1)[1].split("## 9.", 1)[0]
    for line in responsibility.splitlines():
        if not re.match(r"\| C[1-4] \|", line):
            continue
        existing_column = line.split("|")[2]
        for value in re.findall(r"`([^`]+)`", existing_column):
            match = re.fullmatch(r"(.*)\{([^}]+)\}(.*)", value)
            paths = [match[1] + part + match[3] for part in match[2].split(",")] if match else [value]
            for value in paths:
                if (root / "产品代码" / value).is_file():
                    origin = "frozen-tree"
                elif subprocess.run(["git", "cat-file", "-e", "8a58b98ecc1bccb7c66a55a44b4c1ca9cf873e93:产品代码/" + value], cwd=repo, capture_output=True).returncode == 0:
                    origin = "R4-exact-commit"
                else:
                    origin = "missing"
                    errors.append("claimed existing plan path missing: " + value)
                path_checks.append({"path": value, "origin": origin})
    report["plan_existing_paths"] = path_checks
    snapshot = json.loads((root / (EVIDENCE + "evidence-snapshot.json")).read_text())
    if snapshot["base"] != BASE or not snapshot["b0_is_r4_ancestor"] or len(snapshot["r4_delta"]) != 12:
        errors.append("source snapshot topology drift")
    for name, tree in snapshot["base_trees"].items():
        actual = git(repo, "rev-parse", target + ":产品代码/" + name).decode().strip()
        if actual != tree:
            errors.append("production tree changed: " + name)
    for item in snapshot["r4_delta"]:
        raw = git(repo, "show", item["commit"] + ":" + item["path"])
        if digest(raw) != item["sha256"]:
            errors.append("R4 exact blob mismatch: " + item["path"])
    external = []
    for item in snapshot["external_files"]:
        path = Path(item["path"])
        if not item["exists"]:
            state = "known-missing" if not path.is_file() else "previously-missing-now-present"
        elif not path.is_file():
            state = "missing-after-snapshot"
        else:
            state = "hash-matched" if digest(path.read_bytes()) == item["sha256"] else "changed-after-snapshot"
        external.append({"path": str(path), "role": item["role"], "state": state})
        # Migration source and advisory attachment are provenance, never startup dependencies.
        if item["role"] == "external-runtime-file-only" and state != "hash-matched":
            errors.append("Runtime reference drift: " + str(path))
    report.update(relative_links_checked=links, prototype_references_checked=prototypes,
                  original_ac_count=len(ac), original_ac_sha256=digest("\n".join(ac).encode()),
                  external_files=external, known_evidence_gaps=["S05 current PPTX hash differs from historical report", "S08 temporary source_copy missing"],
                  baseline_hashes={n: digest((root / n).read_bytes()) for n in BASELINES},
                  plan_sha256=digest((root / PLAN).read_bytes()), errors=errors, result="PASS" if not errors else "FAIL")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
