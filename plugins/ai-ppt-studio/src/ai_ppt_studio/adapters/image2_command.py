"""Host-configured Image 2 command adapter; never configured by public input.

AI_PPT_IMAGE2_ADAPTER_COMMAND is a JSON argv array with an absolute executable.
AI_PPT_IMAGE2_RECEIVER / AI_PPT_IMAGE2_MODEL declare the configured destination.
An optional AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST names credential variables the
host explicitly permits the adapter to inherit; confirmation secrets are denied.
The command receives one JSON object on stdin and returns one on stdout using
image-led-image2-transport/v1. It must implement its provider call exactly once.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from ai_ppt_studio.domains.materials.image_input_contracts import exact, fail, text
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.adapters.image2_diagnostics import (
    CommandFailure, CommandContractFailure, diagnostic, parse_failure,
)

PROTOCOL = "image-led-image2-transport/v1"


def _known_crs_command(command, receiver, model):
    from ai_ppt_studio.adapters.image2_crs import MODEL, SUNBURST_MODEL
    wrapper = str(Path(__file__).resolve().with_name('image2_crs.py'))
    if receiver != 'CRS' or model not in (MODEL, SUNBURST_MODEL):
        return False
    expected = (sys.executable, wrapper) + (() if model == MODEL else ('--model', SUNBURST_MODEL))
    return Path(sys.executable).is_absolute() and tuple(command) == expected


class Image2CommandAdapter:
    def __init__(self, command, receiver, model, environment):
        self.command = command
        self.receiver = receiver
        self.model = model
        self.environment = environment

    @classmethod
    def from_environment(cls):
        """Read only host configuration; missing capability performs no writes."""
        try:
            command = json.loads(os.environ.get("AI_PPT_IMAGE2_ADAPTER_COMMAND", ""))
            allowed = json.loads(os.environ.get("AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST", "[]"))
        except (json.JSONDecodeError, TypeError):
            fail("CAPABILITY_GAP", "Image 2 host command adapter is not configured")
        if (not isinstance(command, list) or not command
                or any(not isinstance(value, str) or not value or "\x00" in value for value in command)):
            fail("CAPABILITY_GAP", "Image 2 host adapter needs an explicit JSON argv array")
        executable = Path(command[0])
        if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
            fail("CAPABILITY_GAP", "Image 2 host adapter executable is unavailable")
        receiver, model = (os.environ.get(key, "") for key in ("AI_PPT_IMAGE2_RECEIVER", "AI_PPT_IMAGE2_MODEL"))
        if not receiver.strip() or not model.strip():
            fail("CAPABILITY_GAP", "Image 2 host adapter destination is not configured")
        if (not isinstance(allowed, list) or any(not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                or key.startswith("AI_PPT_") for key in allowed)):
            fail("CAPABILITY_GAP", "Image 2 adapter environment allowlist is invalid")
        environment = {key: os.environ[key] for key in {"PATH", "LANG", "LC_ALL", "TMPDIR", *allowed}
                       if key in os.environ}
        return cls(tuple(command), receiver, model, environment)

    def preflight(self, payload):
        if payload.get("receiver") != self.receiver or payload.get("model") != self.model:
            fail("UNAUTHORIZED", "configured Image 2 adapter differs from the authorized receiver or model")
        protocol = generation_protocol(payload)
        wrapper = str(Path(__file__).resolve().with_name('image2_crs.py'))
        if (protocol != PROTOCOL or self.receiver == 'CRS'
                or self.model == 'gpt-image-2.5-sunburst' or wrapper in self.command):
            if not _known_crs_command(self.command, self.receiver, self.model):
                fail('CAPABILITY_GAP', 'execution command differs from the known CRS model binding')
            # Pure serialization catches unsupported data before a queued task or call.
            from ai_ppt_studio.adapters.image2_crs import compile_body
            try:
                compile_body({'protocol':protocol,'request_id':'local-preflight','payload':payload}, model=self.model)
            except Exception:
                fail('CAPABILITY_GAP', 'Image 2 payload is not executable')
            capability = image2_preflight(generation_protocol=None if protocol == PROTOCOL else protocol,
                _expected_identity=(self.command, self.receiver, self.model))
            if capability['protocol_probe'] != 'passed':
                fail('CAPABILITY_GAP', 'current Image 2 wrapper does not support the required transport')

    def generate(self, *, request_id, payload):
        self.preflight(payload)
        protocol = generation_protocol(payload)
        request = {"protocol": protocol, "request_id": request_id, "payload": deepcopy(payload)}
        # No shell and no inherited host confirmation credentials. No retry here:
        # nonzero exits/invalid output become a persistent unknown service result.
        request_bytes = json.dumps(request, ensure_ascii=False).encode("utf-8")
        try:
            completed = subprocess.run(self.command, input=request_bytes,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=self.environment, check=False)
        except OSError:
            raise CommandFailure(diagnostic('subprocess', 'subprocess-failed')) from None
        if completed.returncode != 0:
            failure = diagnostic('subprocess', 'subprocess-failed', exit_code=completed.returncode)
            if _known_crs_command(self.command, self.receiver, self.model):
                try:
                    failure = parse_failure(completed.stdout, request_bytes, completed.returncode)
                except ValueError:
                    pass
            raise CommandFailure(failure)
        try:
            from ai_ppt_studio.adapters.image2_crs import load_json
            from ai_ppt_studio.domains.visual.image_output import validate_provider_observation
            response = load_json(completed.stdout)
            fields = {"protocol", "receiver", "model", "request_id", "response_id", "image_base64"}
            observation_required = protocol != PROTOCOL and _known_crs_command(self.command, self.receiver, self.model)
            has_observation = isinstance(response, dict) and 'provider_observation' in response
            exact(response, fields | ({'provider_observation'} if has_observation or observation_required else set()),
                  "Image 2 adapter response")
            if (response["protocol"] != protocol or response["receiver"] != self.receiver
                    or response["model"] != self.model or response["request_id"] != request_id):
                raise ValueError("response identity mismatch")
            text(response["response_id"], "response_id")
            raw = base64.b64decode(response["image_base64"], validate=True)
            observed = ({'provider_observation': validate_provider_observation(response['provider_observation'],
                receiver=self.receiver, model=self.model)} if has_observation else {})
        except ContractValidationError:
            raise CommandContractFailure(diagnostic('adapter-receipt', 'adapter-receipt-invalid',
                exit_code=completed.returncode)) from None
        except (ValueError, TypeError, KeyError, RecursionError):
            raise CommandFailure(diagnostic('adapter-receipt', 'adapter-receipt-invalid',
                exit_code=completed.returncode)) from None
        return {"response_id": response["response_id"], "image_bytes": raw, **observed}


def generation_protocol(payload):
    if 'payload_version' not in payload:
        return PROTOCOL
    if payload['payload_version'] == 'image-led-image2-input/v2':
        return 'image-led-image2-transport/v2'
    if payload['payload_version'] == 'image-led-image2-repair-input/v1':
        return 'image-led-image2-repair-transport/v1'
    fail('VERSION', 'unsupported Image 2 payload version')


PREFLIGHT_PROTOCOL = "image-led-image2-preflight/v1"
PREFLIGHT_KEYS = (
    "AI_PPT_IMAGE2_ADAPTER_COMMAND", "AI_PPT_IMAGE2_RECEIVER",
    "AI_PPT_IMAGE2_MODEL", "AI_PPT_IMAGE2_ADAPTER_ENV_ALLOWLIST",
)


def _unique_probe_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate probe field")
        result[key] = value
    return result


def image2_preflight(*, generation_protocol=None, _expected_identity=None):
    """Observe this Python process; never execute an arbitrary configured argv.

    No business writes, credential reads, helper execution or HTTP. Identity
    comes from the currently loaded package path and its bytes, not a basename,
    a caller-supplied hash, or shell environment observed by another process.
    """
    wrapper = Path(__file__).resolve().with_name("image2_crs.py")
    result = {
        "configuration_presence": {key: key in os.environ for key in PREFLIGHT_KEYS},
        "known_wrapper": False,
        "protocol_probe": "unavailable",
        "helper_executable": None,
        "external_connection": "not-tested",
        "wrapper_sha256": None,
        "probe_nonce": uuid.uuid4().hex,
    }
    try:
        result["wrapper_sha256"] = hashlib.sha256(wrapper.read_bytes()).hexdigest()
    except OSError:
        return result
    if not all(result["configuration_presence"][key] for key in PREFLIGHT_KEYS[:3]):
        return result
    result["protocol_probe"] = "failed"
    try:
        command = json.loads(os.environ[PREFLIGHT_KEYS[0]])
        allowed = json.loads(os.environ.get(PREFLIGHT_KEYS[3], "[]"))
        receiver, model = (os.environ[key] for key in PREFLIGHT_KEYS[1:3])
        if (not isinstance(command, list) or not command
                or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in command)
                or not receiver.strip() or not model.strip()
                or not isinstance(allowed, list)
                or any(not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                       or key.startswith("AI_PPT_") for key in allowed)):
            return result
        # Deliberately do not resolve caller argv or accept basename aliases.
        # Exact paths and the bounded optional model select one known identity.
        if (not _known_crs_command(command, receiver, model)
                or (_expected_identity is not None
                    and (tuple(command), receiver, model) != _expected_identity)):
            result["protocol_probe"] = "unsupported"
            return result
        result["known_wrapper"] = True
        v2 = generation_protocol in ('image-led-image2-transport/v2', 'image-led-image2-repair-transport/v1')
        if generation_protocol not in (None, 'image-led-image2-transport/v2', 'image-led-image2-repair-transport/v1'):
            return result
        if generation_protocol == 'image-led-image2-repair-transport/v1' and model != 'gpt-image-2':
            return result
        probe_protocol = 'image-led-image2-preflight/v2' if v2 else PREFLIGHT_PROTOCOL
        request = {"protocol": probe_protocol, "request_id": result["probe_nonce"],
                   **({'generation_protocol':generation_protocol} if v2 else {})}
        # A preflight needs no provider secrets or Python startup/module hooks,
        # even if the generation adapter's host allowlist permits those values.
        environment = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TMPDIR") if key in os.environ}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run([*command, "--preflight"],
            input=json.dumps(request).encode("utf-8"), stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=environment, timeout=10, check=False)
        # subprocess.run kills and reaps the direct child on timeout; no
        # descendant-termination guarantee is implied by this local probe.
        if completed.returncode != 0:
            return result
        probe = json.loads(completed.stdout, object_pairs_hook=_unique_probe_object)
        if (not isinstance(probe, dict) or set(probe) != ({
                "protocol", "request_id", "receiver", "model", "helper_executable", "external_connection"}
                | ({'generation_protocol'} if v2 else set()))
                or probe["protocol"] != probe_protocol
                or (v2 and probe['generation_protocol'] != generation_protocol)
                or probe["request_id"] != result["probe_nonce"]
                or probe["receiver"] != "CRS" or probe["model"] != model
                or type(probe["helper_executable"]) is not bool
                or probe["external_connection"] != "not-tested"):
            return result
        result["protocol_probe"] = "passed"
        result["helper_executable"] = probe["helper_executable"]
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        # Only the fixed safe fields above cross the public bridge.
        pass
    return result
