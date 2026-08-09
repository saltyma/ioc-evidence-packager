"""Headless analyst-reasoning, local-intelligence, and provider use cases."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from ioc_evidence_packager.application.ports import WorkspaceRepository
from ioc_evidence_packager.domain.analysis import AnalysisSnapshot
from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.domain.evidence import EvidenceRecord
from ioc_evidence_packager.domain.models import Case, CaseId, PrivacyMode
from ioc_evidence_packager.domain.observables import parse_observable
from ioc_evidence_packager.domain.workspace import (
    AssertionId,
    IntelligenceAssertion,
    IntelligenceClaim,
    Recommendation,
    RecommendationId,
    RecommendationStatus,
    RelationshipSnapshot,
    build_recommendations,
    build_relationships,
    legacy_recommendation_id,
)

INTELLIGENCE_SCHEMA = "ioc-intelligence-assertions/1.0.0"
MAX_ASSERTION_FILE_BYTES = 2_000_000
MAX_PROVIDER_RESPONSE_BYTES = 2_000_000


class WorkspaceService:
    """Builds deterministic reasoning output and overlays durable analyst state."""

    def __init__(self, repository: WorkspaceRepository) -> None:
        self._repository = repository

    def relationships(self, records: tuple[EvidenceRecord, ...]) -> RelationshipSnapshot:
        return build_relationships(records)

    def recommendations(
        self,
        case_id: CaseId,
        analysis: AnalysisSnapshot | None,
        relationships: RelationshipSnapshot,
    ) -> tuple[Recommendation, ...]:
        states = self._repository.recommendation_states(case_id)
        values: list[Recommendation] = []
        for item in build_recommendations(analysis, relationships):
            state = states.get(item.recommendation_id)
            if state is None:
                legacy_id = legacy_recommendation_id(item)
                state = states.get(legacy_id)
                if state is not None and legacy_id != item.recommendation_id:
                    self._repository.set_recommendation_state(
                        case_id, item.recommendation_id, state[0], state[1], state[2]
                    )
            values.append(item.with_state(*state) if state is not None else item)
        return tuple(values)

    def set_recommendation_state(
        self,
        case_id: CaseId,
        recommendation_id: RecommendationId,
        status: RecommendationStatus,
        note: str | None,
    ) -> None:
        normalized = note.strip() if note and note.strip() else None
        if status is RecommendationStatus.DISMISSED and not normalized:
            raise ValidationError("A dismissal needs an analyst reason.")
        self._repository.set_recommendation_state(
            case_id, recommendation_id, status, normalized, datetime.now(UTC)
        )

    def assertions(self, case_id: CaseId) -> tuple[IntelligenceAssertion, ...]:
        return self._repository.list_assertions(case_id)

    def add_manual_assertion(
        self,
        case_id: CaseId,
        *,
        provider: str,
        observable_type: str,
        observable_value: str,
        claim: IntelligenceClaim,
        confidence_label: str,
        summary: str,
        source_reference: str | None = None,
    ) -> IntelligenceAssertion:
        values = [provider, observable_type, observable_value, confidence_label, summary]
        if any(not value.strip() for value in values):
            raise ValidationError("Provider, observable, confidence, and summary are required.")
        canonical_type, canonical_value = _canonical_observable(observable_type, observable_value)
        assertion = IntelligenceAssertion(
            assertion_id=AssertionId(f"assertion-{uuid4()}"),
            case_id=case_id,
            provider=provider.strip()[:120],
            provider_version="analyst-entry/1.0.0",
            observable_type=canonical_type,
            observable_value=canonical_value,
            claim=claim,
            confidence_label=confidence_label.strip()[:120],
            summary=summary.strip()[:4000],
            retrieved_at=datetime.now(UTC),
            source_reference=source_reference.strip()[:2048] if source_reference else None,
            origin="manual",
        )
        self._repository.add_assertion(assertion)
        return assertion

    def import_assertions(self, case_id: CaseId, path: Path) -> int:
        try:
            if path.stat().st_size > MAX_ASSERTION_FILE_BYTES:
                raise ValidationError("The intelligence file exceeds the 2 MB safety limit.")
            raw = path.read_bytes()
            document = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValidationError(f"Could not read intelligence assertions: {error}") from error
        if not isinstance(document, dict) or document.get("schema") != INTELLIGENCE_SCHEMA:
            raise ValidationError(f"Expected schema {INTELLIGENCE_SCHEMA}.")
        values = document.get("assertions")
        if not isinstance(values, list) or len(values) > 500:
            raise ValidationError("Assertions must be a JSON list with at most 500 entries.")
        digest = hashlib.sha256(raw).hexdigest()
        assertions: list[IntelligenceAssertion] = []
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                raise ValidationError(f"Assertion {index + 1} must be an object.")
            try:
                retrieved = _parse_time(item.get("retrieved_at")) or datetime.now(UTC)
                observable_type, observable_value = _canonical_observable(
                    _required(item, "observable_type", index, 40),
                    _required(item, "observable_value", index, 2048),
                )
                raw_response_sha256 = _optional_sha256(item.get("raw_response_sha256"), digest)
                assertion = IntelligenceAssertion(
                    assertion_id=AssertionId(
                        "assertion-import-"
                        + hashlib.sha256(f"{case_id}:{digest}:{index}".encode()).hexdigest()[:24]
                    ),
                    case_id=case_id,
                    provider=_required(item, "provider", index, 120),
                    provider_version=str(item.get("provider_version") or "import/1.0.0")[:120],
                    observable_type=observable_type,
                    observable_value=observable_value,
                    claim=IntelligenceClaim(_required(item, "claim", index, 40)),
                    confidence_label=_required(item, "confidence_label", index, 120),
                    summary=_required(item, "summary", index, 4000),
                    retrieved_at=retrieved,
                    data_timestamp=_parse_time(item.get("data_timestamp")),
                    expires_at=_parse_time(item.get("expires_at")),
                    source_reference=(
                        str(item["source_reference"])[:2048]
                        if item.get("source_reference")
                        else None
                    ),
                    raw_response_sha256=raw_response_sha256,
                    origin="import",
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValidationError(f"Assertion {index + 1} is invalid: {error}") from error
            assertions.append(assertion)
        return self._repository.add_assertions(tuple(assertions))

    def archive_assertion(self, case_id: CaseId, assertion_id: AssertionId) -> None:
        self._repository.archive_assertion(case_id, assertion_id)

    def query_virustotal(
        self,
        case: Case,
        observable_type: str,
        value: str,
        *,
        cache_hours: int = 24,
    ) -> IntelligenceAssertion:
        """Retrieve one existing object report; never uploads evidence or samples."""

        if case.privacy_mode not in {PrivacyMode.SAFE_ENRICHMENT, PrivacyMode.ENTERPRISE}:
            raise ValidationError(
                "Remote lookups require Safe enrichment or Enterprise privacy mode."
            )
        observable_type, value = _canonical_observable(observable_type, value)
        now = datetime.now(UTC)
        cached = next(
            (
                item
                for item in self._repository.list_assertions(case.case_id)
                if item.provider == "VirusTotal"
                and item.observable_type == observable_type
                and item.observable_value == value
                and item.expires_at is not None
                and item.expires_at >= now
            ),
            None,
        )
        if cached is not None:
            return cached
        api_key = os.environ.get("IOC_PACKAGER_VT_API_KEY", "").strip()
        if not api_key:
            raise ValidationError("Set IOC_PACKAGER_VT_API_KEY in the launch environment first.")
        collection = {"ipv4": "ip_addresses", "domain": "domains", "sha256": "files"}.get(
            observable_type
        )
        if collection is None:
            raise ValidationError("VirusTotal lookup supports IPv4, domain, and SHA-256 values.")
        encoded = urllib.parse.quote(value, safe="")
        url = f"https://www.virustotal.com/api/v3/{collection}/{encoded}"
        request = urllib.request.Request(  # noqa: S310 - fixed HTTPS origin
            url, headers={"x-apikey": api_key, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=12) as response:  # noqa: S310 - fixed HTTPS origin
                raw = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise ValidationError(f"VirusTotal lookup failed: {error}") from error
        if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
            raise ValidationError("VirusTotal response exceeded the 2 MB safety limit.")
        try:
            body: dict[str, Any] = json.loads(raw)
            attributes = body["data"]["attributes"]
            stats = attributes.get("last_analysis_stats", {})
            malicious = int(stats.get("malicious", 0))
            suspicious = int(stats.get("suspicious", 0))
            harmless = int(stats.get("harmless", 0))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValidationError("VirusTotal returned an unexpected object response.") from error
        claim = (
            IntelligenceClaim.MALICIOUS
            if malicious > 0
            else IntelligenceClaim.SUSPICIOUS
            if suspicious > 0
            else IntelligenceClaim.BENIGN
            if harmless > 0
            else IntelligenceClaim.UNKNOWN
        )
        retrieved = datetime.now(UTC)
        assertion = IntelligenceAssertion(
            assertion_id=AssertionId(f"assertion-{uuid4()}"),
            case_id=case.case_id,
            provider="VirusTotal",
            provider_version="api-v3/object-report",
            observable_type=observable_type,
            observable_value=value,
            claim=claim,
            confidence_label=(
                f"native detections: malicious {malicious}, suspicious {suspicious}, "
                f"harmless {harmless}"
            ),
            summary=(
                "Existing VirusTotal object report. Counts are provider-native engine "
                "classifications, not an IOC Evidence Packager risk score."
            ),
            retrieved_at=retrieved,
            data_timestamp=_unix_time(attributes.get("last_analysis_date")),
            expires_at=retrieved + timedelta(hours=max(1, min(168, cache_hours))),
            source_reference="https://www.virustotal.com/gui/"
            + {"files": "file", "ip_addresses": "ip-address", "domains": "domain"}[collection]
            + f"/{encoded}",
            raw_response_sha256=hashlib.sha256(raw).hexdigest(),
            origin="virustotal",
        )
        self._repository.add_assertion(assertion)
        return assertion


def _required(item: dict[str, Any], key: str, index: int, max_length: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Assertion {index + 1} requires {key}.")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise ValidationError(f"Assertion {index + 1} field {key} exceeds {max_length} characters.")
    return normalized


def _canonical_observable(observable_type: str, value: str) -> tuple[str, str]:
    declared = observable_type.strip().casefold()
    parsed = parse_observable(value)
    if parsed.observable_type.value != declared:
        raise ValidationError(
            f"Observable type {declared or '(empty)'} does not match "
            f"the validated {parsed.observable_type.value} value."
        )
    return parsed.observable_type.value, parsed.canonical_value


def _optional_sha256(value: Any, default: str) -> str:
    if value in (None, ""):
        return default
    if not isinstance(value, str) or len(value) != 64:
        raise ValidationError("raw_response_sha256 must be 64 hexadecimal characters.")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValidationError("raw_response_sha256 must be 64 hexadecimal characters.") from error
    return value.casefold()


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValidationError("Timestamps must be ISO-8601 strings.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValidationError("Timestamps must include a timezone.")
    return parsed


def _unix_time(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), UTC) if value is not None else None
    except (TypeError, ValueError, OSError):
        return None
