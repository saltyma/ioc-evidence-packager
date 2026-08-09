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

CAPSULE_SCHEMA = "1.1.0"
EVIDENCE_SCHEMA = "evidence-record/1.0.0"
COVERAGE_SCHEMA = "coverage/1.0.0"
SOURCE_SCHEMA = "source-inventory/1.1.0"
RELATIONSHIP_SCHEMA = "relationship-graph/1.0.0"
RECOMMENDATION_SCHEMA = "recommendations/1.0.0"
INTELLIGENCE_SCHEMA = "intelligence-assertions/1.0.0"

ARTIFACTS = (
    ("report.html", "text/html", "human-readable report"),
    ("evidence.jsonl", "application/x-ndjson", "source-linked evidence"),
    ("timeline.csv", "text/csv", "deterministic timeline"),
    ("coverage.json", "application/json", "coverage matrix"),
    ("source-inventory.json", "application/json", "source inventory"),
    ("relationships.json", "application/json", "evidence-backed relationship graph"),
    ("recommendations.json", "application/json", "rule-explained next actions"),
    ("intelligence.json", "application/json", "attributed intelligence assertions"),
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

    expected = {name for name, _media_type, _role in ARTIFACTS}
    for missing in sorted(expected - seen):
        messages.append(f"Required artifact is missing from manifest: {missing}")
    for unexpected in sorted(seen - expected):
        messages.append(f"Unexpected artifact in manifest: {unexpected}")

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
    relationships = _relationship_projection(report, profile, salt)
    recommendations = [_recommendation_projection(item, profile) for item in report.recommendations]
    intelligence = [_intelligence_projection(item, profile) for item in report.intelligence]
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
        "relationships": relationships,
        "recommendations": recommendations,
        "intelligence": intelligence,
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
        "format": preview.format_name,
        "sample_records": preview.sample_records,
        "mapped_fields": list(preview.fields),
        "capabilities": list(preview.capabilities),
        "accepted_records": accepted,
        "rejected_records": rejected,
        "warnings": list(preview.warnings),
        "earliest_time": preview.earliest_time.isoformat() if preview.earliest_time else None,
        "latest_time": preview.latest_time.isoformat() if preview.latest_time else None,
    }


def _relationship_projection(
    report: CaseReport, profile: ExportProfile, salt: str
) -> dict[str, Any]:
    redacted = profile is ExportProfile.REDACTED_SHAREABLE
    entity_ids = {
        node.entity_id: (
            f"entity-redacted-{hashlib.sha256(f'{salt}|{node.entity_type.value}|{node.value}'.encode()).hexdigest()[:20]}"
            if redacted and node.entity_type.value in {"host", "user"}
            else str(node.entity_id)
        )
        for node in report.relationships.nodes
    }
    nodes = []
    for node in report.relationships.nodes:
        value = node.value
        if redacted and node.entity_type.value in {"host", "user"}:
            value = _pseudonym(node.entity_type.value.upper(), value, salt) or "REDACTED"
        nodes.append(
            {
                "entity_id": entity_ids[node.entity_id],
                "entity_type": node.entity_type.value,
                "value": value,
                "evidence_ids": list(node.evidence_ids),
            }
        )
    edges = [
        {
            "relationship_id": str(edge.relationship_id),
            "from": entity_ids[edge.source_id],
            "to": entity_ids[edge.target_id],
            "relation": edge.relation,
            "rule_id": edge.rule_id,
            "explanation": edge.explanation,
            "evidence_ids": list(edge.evidence_ids),
        }
        for edge in report.relationships.edges
    ]
    return {"schema": RELATIONSHIP_SCHEMA, "nodes": nodes, "edges": edges}


def _recommendation_projection(item: Any, profile: ExportProfile) -> dict[str, Any]:
    return {
        "recommendation_id": str(item.recommendation_id),
        "rule": f"{item.rule_id}/{item.rule_version}",
        "priority": item.priority.value,
        "status": item.status.value,
        "category": item.category,
        "title": item.title,
        "rationale": item.rationale,
        "expected_value": item.expected_value,
        "safety_note": item.safety_note,
        "action": item.action,
        "evidence_ids": list(item.evidence_ids),
        "coverage_cell_ids": list(item.coverage_cell_ids),
        "relationship_ids": list(item.relationship_ids),
        "analyst_note": (
            None if profile is ExportProfile.REDACTED_SHAREABLE else item.analyst_note
        ),
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _intelligence_projection(item: Any, profile: ExportProfile) -> dict[str, Any]:
    return {
        "assertion_id": str(item.assertion_id),
        "provider": item.provider,
        "provider_version": item.provider_version,
        "origin": item.origin,
        "observable_type": item.observable_type,
        "observable_value": item.observable_value,
        "claim": item.claim.value,
        "confidence_label": item.confidence_label,
        "summary": item.summary,
        "retrieved_at": item.retrieved_at.isoformat(),
        "data_timestamp": item.data_timestamp.isoformat() if item.data_timestamp else None,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "source_reference": (
            None if profile is ExportProfile.REDACTED_SHAREABLE else item.source_reference
        ),
        "raw_response_sha256": item.raw_response_sha256,
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
    _write_json(root / "relationships.json", projection["relationships"])
    _write_json(
        root / "recommendations.json",
        {"schema": RECOMMENDATION_SCHEMA, "recommendations": projection["recommendations"]},
    )
    _write_json(
        root / "intelligence.json",
        {"schema": INTELLIGENCE_SCHEMA, "assertions": projection["intelligence"]},
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
    redacted = projection["profile"] == ExportProfile.REDACTED_SHAREABLE.value
    return template.render(
        title="Redacted IOC Evidence Case" if redacted else report.case.title,
        reference=None if redacted else report.case.external_reference,
        summary=(
            "Case-identifying title, reference, and summary were omitted by the shareable profile."
            if redacted
            else report.case.summary
        ),
        profile=projection["profile"],
        lead=(f"{lead.observable_type.value.upper()} · {lead.canonical_value}" if lead else "None"),
        recipe=f"{report.analysis.recipe_id}/{report.analysis.recipe_version}",
        direct_count=len(report.analysis.sightings),
        evidence=projection["evidence"],
        coverage=projection["coverage"],
        sources=projection["sources"],
        relationships=projection["relationships"],
        recommendations=projection["recommendations"],
        intelligence=projection["intelligence"],
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
        "case_id": (
            _pseudonym("CASE", str(report.case.case_id), str(export_id))
            if profile is ExportProfile.REDACTED_SHAREABLE
            else str(report.case.case_id)
        ),
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
        evidence_rows = [
            json.loads(line)
            for line in (root / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if any(
            not isinstance(row, dict) or not isinstance(row.get("evidence_id"), str)
            for row in evidence_rows
        ):
            raise ValueError("evidence.jsonl contains an invalid evidence record")
        evidence_ids = {row["evidence_id"] for row in evidence_rows}
        coverage: dict[str, Any] = json.loads((root / "coverage.json").read_text(encoding="utf-8"))
        coverage_cells = _object_list(coverage, "cells")
        referenced = {
            str(value) for cell in coverage_cells for value in _string_list(cell, "evidence_ids")
        }
        coverage_ids = {
            str(cell["coverage_cell_id"])
            for cell in coverage_cells
            if isinstance(cell.get("coverage_cell_id"), str)
        }
        if len(coverage_ids) != len(coverage_cells):
            raise ValueError("coverage.json contains an invalid coverage cell")
        relationships: dict[str, Any] = json.loads(
            (root / "relationships.json").read_text(encoding="utf-8")
        )
        edges = _object_list(relationships, "edges")
        nodes = _object_list(relationships, "nodes")
        relationship_evidence = {
            str(value) for item in (*edges, *nodes) for value in _string_list(item, "evidence_ids")
        }
        relationship_ids = {
            str(edge["relationship_id"])
            for edge in edges
            if isinstance(edge.get("relationship_id"), str)
        }
        if len(relationship_ids) != len(edges):
            raise ValueError("relationships.json contains an invalid relationship")
        recommendations: dict[str, Any] = json.loads(
            (root / "recommendations.json").read_text(encoding="utf-8")
        )
        recommendation_items = _object_list(recommendations, "recommendations")
        recommendation_evidence = {
            str(value)
            for item in recommendation_items
            for value in _string_list(item, "evidence_ids")
        }
        recommendation_relationships = {
            str(value)
            for item in recommendation_items
            for value in _string_list(item, "relationship_ids")
        }
        recommendation_coverage = {
            str(value)
            for item in recommendation_items
            for value in _string_list(item, "coverage_cell_ids")
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        messages.append(f"Machine-readable artifact validation failed: {error}")
        return
    missing = (referenced | relationship_evidence | recommendation_evidence) - evidence_ids
    if missing:
        messages.append(f"Coverage references {len(missing)} missing evidence ID(s).")
    missing_relationships = recommendation_relationships - relationship_ids
    if missing_relationships:
        messages.append(
            f"Recommendations reference {len(missing_relationships)} missing relationship ID(s)."
        )
    missing_coverage = recommendation_coverage - coverage_ids
    if missing_coverage:
        messages.append(
            f"Recommendations reference {len(missing_coverage)} missing coverage cell ID(s)."
        )


def _object_list(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be a list of objects")
    return value


def _string_list(document: dict[str, Any], key: str) -> list[str]:
    value = document.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return value


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
<h2>Relationships</h2><div class="card"><p class="muted">{{ relationships.nodes|length }} typed nodes · {{ relationships.edges|length }} evidence-backed edges. Each edge is contextual and cites source evidence.</p><table><thead><tr><th>Relationship</th><th>Rule</th><th>Supporting evidence</th></tr></thead><tbody>{% for edge in relationships.edges %}<tr><td><code>{{ edge.from }}</code> · {{ edge.relation }} · <code>{{ edge.to }}</code></td><td>{{ edge.rule_id }}</td><td>{{ edge.evidence_ids|length }}</td></tr>{% endfor %}</tbody></table></div>
<h2>Recommendations</h2><div class="card"><table><thead><tr><th>Priority / state</th><th>Action</th><th>Why</th><th>Rule</th></tr></thead><tbody>{% for item in recommendations %}<tr><td>{{ item.priority }}<br><code>{{ item.status }}</code></td><td>{{ item.title }}<br>{{ item.action }}</td><td>{{ item.rationale }}<br><span class="muted">Safety: {{ item.safety_note }}</span></td><td>{{ item.rule }}</td></tr>{% endfor %}</tbody></table></div>
<h2>Intelligence assertions</h2><div class="card"><p class="muted">Attributed context only; these claims do not alter evidence classification.</p><table><thead><tr><th>Provider</th><th>Observable</th><th>Claim</th><th>Provider confidence</th><th>Retrieved</th></tr></thead><tbody>{% for item in intelligence %}<tr><td>{{ item.provider }}</td><td>{{ item.observable_type }} · <code>{{ item.observable_value }}</code></td><td>{{ item.claim }}</td><td>{{ item.confidence_label }}</td><td>{{ item.retrieved_at }}</td></tr>{% endfor %}</tbody></table></div>
<h2>Source inventory</h2><div class="card"><table><thead><tr><th>Source</th><th>Status</th><th>Adapter</th><th>Accepted / rejected</th><th>SHA-256</th></tr></thead><tbody>{% for source in sources %}<tr><td>{{ source.name }}</td><td>{{ source.status }}</td><td>{{ source.adapter or "Unsupported" }}</td><td>{{ source.accepted_records }} / {{ source.rejected_records }}</td><td><code>{{ source.sha256 or "Unavailable" }}</code></td></tr>{% endfor %}</tbody></table></div>
<h2>Limitations</h2><div class="card">{% if limitations %}<ul>{% for item in limitations %}<li class="warn">{{ item }}</li>{% endfor %}</ul>{% else %}<p>No coverage limitation was recorded for the implemented recipe steps. This is not a declaration that the environment is safe.</p>{% endif %}</div>
<p class="muted">Portable offline projection. Verify manifest.json before relying on these artifacts. Source digests prove byte identity, not acquisition custody.</p>
</main></body></html>"""
