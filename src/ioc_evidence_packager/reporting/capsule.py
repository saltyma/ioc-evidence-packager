# ruff: noqa: E501 - embedded self-contained HTML template keeps readable markup lines
"""Deterministic, offline Case Capsule rendering and verification."""

import csv
import hashlib
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from jinja2 import BaseLoader, Environment, StrictUndefined, select_autoescape

from ioc_evidence_packager import __version__
from ioc_evidence_packager.domain.analysis import CoverageState, Sighting
from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.domain.evidence import EvidenceRecord
from ioc_evidence_packager.reporting.models import (
    ArtifactDigest,
    CapsuleResult,
    CaseReport,
    ExportId,
    ExportProfile,
    VerificationResult,
)

CAPSULE_SCHEMA = "1.0.0"
EVIDENCE_SCHEMA = "evidence-record/1.0.0"
COVERAGE_SCHEMA = "coverage/1.0.0"
SOURCE_SCHEMA = "source-inventory/1.0.0"

ARTIFACTS = (
    ("report.html", "text/html", "human-readable report"),
    ("evidence.jsonl", "application/x-ndjson", "source-linked evidence"),
    ("timeline.csv", "text/csv", "deterministic timeline"),
    ("coverage.json", "application/json", "coverage matrix"),
    ("source-inventory.json", "application/json", "source inventory"),
)


def export_capsule(
    report: CaseReport,
    destination: Path,
    profile: ExportProfile,
    export_id: ExportId,
    created_at: datetime,
) -> CapsuleResult:
    """Render, hash, verify, and atomically publish a new capsule directory."""

    target = _validated_destination(destination)
    staging = target.parent / f".{target.name}.staging-{uuid4().hex}"
    staging.mkdir(parents=False, exist_ok=False)
    try:
        projection = _build_projection(report, profile, export_id)
        _write_artifacts(staging, projection)
        digests = tuple(
            _artifact_digest(staging / name, name, media_type, role)
            for name, media_type, role in ARTIFACTS
        )
        manifest = _manifest(report, profile, export_id, created_at, digests)
        _write_json(staging / "manifest.json", manifest)
        verification = verify_capsule(staging)
        if not verification.valid:
            raise ValidationError(
                "Capsule verification failed: " + "; ".join(verification.messages)
            )
        os.replace(staging, target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    manifest_sha256 = _sha256(target / "manifest.json")
    return CapsuleResult(
        export_id=export_id,
        case_id=report.case.case_id,
        profile=profile,
        destination=target,
        created_at=created_at,
        manifest_sha256=manifest_sha256,
        artifacts=digests,
    )


def verify_capsule(path: Path) -> VerificationResult:
    """Verify safe paths, artifact set, sizes, hashes, and evidence references."""

    root = path.expanduser().resolve(strict=False)
    messages: list[str] = []
    manifest_path = root / "manifest.json"
    if not root.is_dir() or not manifest_path.is_file():
        return VerificationResult(root, False, 0, ("manifest.json is missing.",))
    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return VerificationResult(root, False, 0, (f"Manifest is unreadable: {error}",))
    if manifest.get("capsule_schema") != CAPSULE_SCHEMA:
        messages.append("Unsupported capsule schema.")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return VerificationResult(root, False, 0, tuple(messages + ["Artifact index is invalid."]))
    seen: set[str] = set()
    checked = 0
    for entry in artifacts:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            messages.append("Artifact entry is invalid.")
            continue
        relative = entry["path"]
        if relative in seen:
            messages.append(f"Duplicate artifact path: {relative}")
            continue
        seen.add(relative)
        if not _safe_relative_path(relative):
            messages.append(f"Unsafe artifact path: {relative}")
            continue
        artifact_path = root.joinpath(*PurePosixPath(relative).parts)
        try:
            artifact_path.resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            messages.append(f"Artifact is missing or escapes the capsule: {relative}")
            continue
        if not artifact_path.is_file():
            messages.append(f"Artifact is not a regular file: {relative}")
            continue
        if artifact_path.stat().st_size != entry.get("byte_size"):
            messages.append(f"Artifact size mismatch: {relative}")
            continue
        if _sha256(artifact_path) != entry.get("sha256"):
            messages.append(f"Artifact hash mismatch: {relative}")
            continue
        checked += 1

    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item.name != "manifest.json"
    }
    for extra in sorted(actual - seen):
        messages.append(f"Unlisted artifact: {extra}")
    for missing in sorted(seen - actual):
        messages.append(f"Listed artifact is missing: {missing}")
    _verify_evidence_references(root, messages)
    if not messages:
        messages.append(f"Verified {checked} artifact(s) against manifest hashes.")
    return VerificationResult(
        root, len(messages) == 1 and messages[0].startswith("Verified"), checked, tuple(messages)
    )


def _build_projection(
    report: CaseReport,
    profile: ExportProfile,
    export_id: ExportId,
) -> dict[str, Any]:
    salt = str(export_id)
    sightings_by_evidence: dict[str, list[Sighting]] = defaultdict(list)
    for sighting in report.analysis.sightings:
        sightings_by_evidence[str(sighting.evidence_id)].append(sighting)
    evidence = [
        _evidence_projection(record, sightings_by_evidence[str(record.evidence_id)], profile, salt)
        for record in report.evidence
    ]
    coverage = [_coverage_projection(cell) for cell in report.analysis.coverage]
    sources = [_source_projection(preview, report, profile) for preview in report.source_previews]
    limitations = [
        cell["reason"]["message"]
        for cell in coverage
        if cell["state"]
        in {
            CoverageState.PARTIAL_COVERAGE.value,
            CoverageState.SOURCE_NOT_PROVIDED.value,
            CoverageState.SOURCE_FAILED.value,
            CoverageState.FORMAT_UNSUPPORTED.value,
        }
    ]
    return {
        "report": report,
        "profile": profile.value,
        "evidence": evidence,
        "coverage": coverage,
        "sources": sources,
        "limitations": limitations,
    }


def _evidence_projection(
    record: EvidenceRecord,
    sightings: list[Sighting],
    profile: ExportProfile,
    salt: str,
) -> dict[str, Any]:
    redacted = profile is ExportProfile.REDACTED_SHAREABLE
    host = _pseudonym("HOST", record.host_name, salt) if redacted else record.host_name
    user = _pseudonym("USER", record.user_name, salt) if redacted else record.user_name
    value: dict[str, Any] = {
        "schema": EVIDENCE_SCHEMA,
        "evidence_id": str(record.evidence_id),
        "classification": "direct_match" if sightings else "context",
        "event_id": record.event_id,
        "occurred_at": record.occurred_at.isoformat() if record.occurred_at else None,
        "category": record.category,
        "action": record.action,
        "host": host,
        "user": user,
        "observables": [
            {
                "kind": item.kind,
                "field_path": item.field_path,
                "original": item.original,
                "canonical": item.canonical,
            }
            for item in record.observables
        ],
        "matches": [
            {
                "sighting_id": str(item.sighting_id),
                "recipe": f"{item.recipe_id}/{item.recipe_version}",
                "step_id": item.step_id,
                "rule_id": item.rule_id,
                "field_path": item.field_path,
                "explanation": item.explanation.text,
            }
            for item in sightings
        ],
        "provenance": {
            "source_name": record.source_name,
            "source_path": None if redacted else str(record.source_path),
            "source_sha256": record.source_sha256,
            "physical_line": record.line_number,
            "declared_source_id": record.declared_source_id,
            "declared_position": {
                "kind": record.declared_position_kind,
                "value": record.declared_position_value,
            },
        },
        "warnings": list(record.warnings),
    }
    if not redacted:
        value["raw_json"] = record.raw_json
    return value


def _coverage_projection(cell: Any) -> dict[str, Any]:
    return {
        "coverage_cell_id": str(cell.cell_id),
        "recipe": f"{cell.recipe_id}/{cell.recipe_version}",
        "step_id": cell.step_id,
        "step_label": cell.step_label,
        "telemetry": cell.telemetry,
        "state": cell.state.value,
        "match_count": cell.match_count,
        "source_preview_ids": [str(value) for value in cell.source_preview_ids],
        "evidence_ids": [str(value) for value in cell.evidence_ids],
        "reason": {
            "code": cell.reason.code,
            "message": cell.reason.message,
            "recovery": cell.reason.recovery,
        },
    }


def _source_projection(preview: Any, report: CaseReport, profile: ExportProfile) -> dict[str, Any]:
    accepted = sum(record.source_preview_id == preview.preview_id for record in report.evidence)
    rejected = sum(item.source_preview_id == preview.preview_id for item in report.rejections)
    return {
        "preview_id": str(preview.preview_id),
        "name": preview.display_name,
        "path": None if profile is ExportProfile.REDACTED_SHAREABLE else str(preview.path),
        "byte_size": preview.byte_size,
        "sha256": preview.sha256,
        "status": preview.status.value,
        "adapter": preview.adapter_id,
        "adapter_version": preview.adapter_version,
        "accepted_records": accepted,
        "rejected_records": rejected,
        "warnings": list(preview.warnings),
        "earliest_time": preview.earliest_time.isoformat() if preview.earliest_time else None,
        "latest_time": preview.latest_time.isoformat() if preview.latest_time else None,
    }


def _write_artifacts(root: Path, projection: dict[str, Any]) -> None:
    _write_text(root / "report.html", _render_html(projection))
    _write_text(
        root / "evidence.jsonl",
        "".join(_json_line(item) for item in projection["evidence"]),
    )
    _write_timeline(root / "timeline.csv", projection["evidence"])
    _write_json(
        root / "coverage.json",
        {"schema": COVERAGE_SCHEMA, "cells": projection["coverage"]},
    )
    _write_json(
        root / "source-inventory.json",
        {"schema": SOURCE_SCHEMA, "sources": projection["sources"]},
    )


def _render_html(projection: dict[str, Any]) -> str:
    environment = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(default=True),
        undefined=StrictUndefined,
    )
    template = environment.from_string(_REPORT_TEMPLATE)
    report: CaseReport = projection["report"]
    lead = report.lead
    return template.render(
        title=report.case.title,
        reference=report.case.external_reference,
        summary=report.case.summary,
        profile=projection["profile"],
        lead=(f"{lead.observable_type.value.upper()} · {lead.canonical_value}" if lead else "None"),
        recipe=f"{report.analysis.recipe_id}/{report.analysis.recipe_version}",
        direct_count=len(report.analysis.sightings),
        evidence=projection["evidence"],
        coverage=projection["coverage"],
        sources=projection["sources"],
        limitations=projection["limitations"],
    )


def _write_timeline(path: Path, evidence: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, dialect="excel", lineterminator="\n")
        writer.writerow(
            (
                "occurred_at",
                "classification",
                "category",
                "action",
                "host",
                "user",
                "source",
                "line",
                "evidence_id",
            )
        )
        for item in evidence:
            provenance = item["provenance"]
            writer.writerow(
                tuple(
                    _spreadsheet_safe(value)
                    for value in (
                        item["occurred_at"] or "",
                        item["classification"],
                        item["category"],
                        item["action"],
                        item["host"] or "",
                        item["user"] or "",
                        provenance["source_name"],
                        provenance["physical_line"],
                        item["evidence_id"],
                    )
                )
            )


def _manifest(
    report: CaseReport,
    profile: ExportProfile,
    export_id: ExportId,
    created_at: datetime,
    artifacts: tuple[ArtifactDigest, ...],
) -> dict[str, Any]:
    return {
        "capsule_schema": CAPSULE_SCHEMA,
        "capsule_id": str(export_id),
        "case_id": str(report.case.case_id),
        "export_profile": profile.value,
        "created_at": created_at.isoformat(),
        "tool": {"name": "ioc-evidence-packager", "version": __version__},
        "run_ids": [str(report.analysis.run_id)],
        "policy_versions": {
            "search_recipe": f"{report.analysis.recipe_id}/{report.analysis.recipe_version}",
            "privacy": f"{report.case.privacy_mode.value}/1.0.0",
            "redaction": "shareable/1.0.0" if profile is ExportProfile.REDACTED_SHAREABLE else None,
        },
        "sources": [
            {
                "preview_id": str(preview.preview_id),
                "name": preview.display_name,
                "sha256": preview.sha256,
                "status": preview.status.value,
            }
            for preview in report.source_previews
        ],
        "artifacts": [
            {
                "path": item.path,
                "media_type": item.media_type,
                "role": item.role,
                "byte_size": item.byte_size,
                "sha256": item.sha256,
            }
            for item in artifacts
        ],
        "warning_summary": {
            "rejected_records": len(report.rejections),
            "coverage_warnings": report.analysis.warning_count,
        },
        "limitations": [
            cell.reason.message
            for cell in report.analysis.coverage
            if cell.state
            in {
                CoverageState.PARTIAL_COVERAGE,
                CoverageState.SOURCE_NOT_PROVIDED,
                CoverageState.SOURCE_FAILED,
                CoverageState.FORMAT_UNSUPPORTED,
            }
        ],
    }


def _artifact_digest(path: Path, name: str, media_type: str, role: str) -> ArtifactDigest:
    return ArtifactDigest(name, media_type, role, path.stat().st_size, _sha256(path))


def _validated_destination(destination: Path) -> Path:
    target = destination.expanduser().resolve(strict=False)
    if target == Path(target.anchor) or not target.name.strip():
        raise ValidationError("Choose a named capsule directory, not a drive root.")
    if target.exists():
        raise ValidationError("The capsule destination already exists; choose a new directory.")
    if not target.parent.is_dir():
        raise ValidationError("The capsule parent directory does not exist.")
    return target


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and "\\" not in value


def _verify_evidence_references(root: Path, messages: list[str]) -> None:
    try:
        evidence_ids = {
            str(json.loads(line)["evidence_id"])
            for line in (root / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        coverage: dict[str, Any] = json.loads((root / "coverage.json").read_text(encoding="utf-8"))
        referenced = {
            str(value)
            for cell in coverage.get("cells", [])
            for value in cell.get("evidence_ids", [])
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        messages.append(f"Machine-readable artifact validation failed: {error}")
        return
    missing = referenced - evidence_ids
    if missing:
        messages.append(f"Coverage references {len(missing)} missing evidence ID(s).")


def _pseudonym(kind: str, value: str | None, salt: str) -> str | None:
    if value is None:
        return None
    digest = hashlib.sha256(f"{salt}|{kind}|{value}".encode()).hexdigest()[:10].upper()
    return f"{kind}-{digest}"


def _spreadsheet_safe(value: object) -> str:
    text = str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def _write_json(path: Path, value: object) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def _json_line(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


_REPORT_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} · IOC Evidence Packager</title>
<style>
:root{color-scheme:dark;--bg:#0d0a12;--panel:#191522;--line:#3b3150;--text:#eeeaf6;--muted:#aaa1ba;--violet:#a78bfa;--amber:#f2b84b;--green:#67d7a4}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:36px}h1{font-size:30px;margin:.2rem 0}h2{margin-top:2rem;border-bottom:1px solid var(--line);padding-bottom:.5rem}.meta,.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}.muted{color:var(--muted)}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.value{font-size:24px;font-weight:750;color:var(--violet)}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted)}code{color:#d9cdfd}.warn{color:var(--amber)}.ok{color:var(--green)}@media(max-width:700px){main{padding:18px}.metrics{grid-template-columns:1fr}}
</style></head><body><main>
<p class="muted">IOC EVIDENCE PACKAGER · {{ profile }}</p><h1>{{ title }}</h1>
<p>{{ summary or "No analyst summary provided." }}</p>
<div class="meta"><strong>Reference:</strong> {{ reference or "Not set" }} · <strong>Lead:</strong> {{ lead }} · <strong>Recipe:</strong> {{ recipe }}</div>
<div class="metrics"><div class="card"><div class="muted">Evidence</div><div class="value">{{ evidence|length }}</div></div><div class="card"><div class="muted">Direct sightings</div><div class="value">{{ direct_count }}</div></div><div class="card"><div class="muted">Coverage limitations</div><div class="value">{{ limitations|length }}</div></div></div>
<h2>Coverage</h2><div class="card"><table><thead><tr><th>Step</th><th>Telemetry</th><th>State</th><th>Reason</th></tr></thead><tbody>{% for cell in coverage %}<tr><td>{{ cell.step_label }}</td><td>{{ cell.telemetry }}</td><td><code>{{ cell.state }}</code></td><td>{{ cell.reason.message }}</td></tr>{% endfor %}</tbody></table></div>
<h2>Evidence ledger</h2><div class="card"><table><thead><tr><th>Time</th><th>Class</th><th>Event</th><th>Host/User</th><th>Source</th></tr></thead><tbody>{% for item in evidence %}<tr><td>{{ item.occurred_at or "Undated" }}</td><td>{{ item.classification }}</td><td>{{ item.category }} · {{ item.action }}{% if item.matches %}<br><span class="ok">{{ item.matches[0].explanation }}</span>{% endif %}</td><td>{{ item.host or "—" }}<br>{{ item.user or "—" }}</td><td>{{ item.provenance.source_name }} line {{ item.provenance.physical_line }}<br><code>{{ item.evidence_id }}</code></td></tr>{% endfor %}</tbody></table></div>
<h2>Source inventory</h2><div class="card"><table><thead><tr><th>Source</th><th>Status</th><th>Adapter</th><th>Accepted / rejected</th><th>SHA-256</th></tr></thead><tbody>{% for source in sources %}<tr><td>{{ source.name }}</td><td>{{ source.status }}</td><td>{{ source.adapter or "Unsupported" }}</td><td>{{ source.accepted_records }} / {{ source.rejected_records }}</td><td><code>{{ source.sha256 or "Unavailable" }}</code></td></tr>{% endfor %}</tbody></table></div>
<h2>Limitations</h2><div class="card">{% if limitations %}<ul>{% for item in limitations %}<li class="warn">{{ item }}</li>{% endfor %}</ul>{% else %}<p>No coverage limitation was recorded for the implemented recipe steps. This is not a declaration that the environment is safe.</p>{% endif %}</div>
<p class="muted">Portable offline projection. Verify manifest.json before relying on these artifacts. Source digests prove byte identity, not acquisition custody.</p>
</main></body></html>"""
