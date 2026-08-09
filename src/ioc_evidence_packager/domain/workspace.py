# ruff: noqa: E501 - rule explanations remain complete and reviewable beside rule code
"""Evidence-backed relationships, recommendations, and intelligence assertions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import NewType

from ioc_evidence_packager.domain.analysis import AnalysisSnapshot, CoverageState
from ioc_evidence_packager.domain.evidence import EvidenceRecord
from ioc_evidence_packager.domain.models import CaseId

EntityId = NewType("EntityId", str)
RelationshipId = NewType("RelationshipId", str)
RecommendationId = NewType("RecommendationId", str)
AssertionId = NewType("AssertionId", str)


class EntityType(StrEnum):
    SOURCE = "source"
    EVENT = "event"
    HOST = "host"
    USER = "user"
    IPV4 = "ipv4"
    DOMAIN = "domain"
    SHA256 = "sha256"
    OBSERVABLE = "observable"


@dataclass(frozen=True, slots=True)
class RelationshipNode:
    entity_id: EntityId
    entity_type: EntityType
    value: str
    label: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceRelationship:
    relationship_id: RelationshipId
    source_id: EntityId
    target_id: EntityId
    relation: str
    rule_id: str
    explanation: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RelationshipSnapshot:
    nodes: tuple[RelationshipNode, ...]
    edges: tuple[EvidenceRelationship, ...]


class RecommendationPriority(StrEnum):
    IMMEDIATE = "Immediate"
    USEFUL = "Useful"
    OPTIONAL = "Optional"


class RecommendationStatus(StrEnum):
    PROPOSED = "Proposed"
    ACCEPTED = "Accepted"
    COMPLETED = "Completed"
    DISMISSED = "Dismissed"


@dataclass(frozen=True, slots=True)
class Recommendation:
    recommendation_id: RecommendationId
    rule_id: str
    rule_version: str
    priority: RecommendationPriority
    category: str
    title: str
    rationale: str
    expected_value: str
    safety_note: str
    action: str
    evidence_ids: tuple[str, ...] = ()
    coverage_cell_ids: tuple[str, ...] = ()
    relationship_ids: tuple[str, ...] = ()
    status: RecommendationStatus = RecommendationStatus.PROPOSED
    analyst_note: str | None = None
    updated_at: datetime | None = None

    def with_state(
        self,
        status: RecommendationStatus,
        note: str | None,
        updated_at: datetime,
    ) -> Recommendation:
        return replace(self, status=status, analyst_note=note, updated_at=updated_at)


class IntelligenceClaim(StrEnum):
    MALICIOUS = "Malicious"
    SUSPICIOUS = "Suspicious"
    BENIGN = "Benign"
    UNKNOWN = "Unknown"
    CONTEXT = "Context only"


@dataclass(frozen=True, slots=True)
class IntelligenceAssertion:
    assertion_id: AssertionId
    case_id: CaseId
    provider: str
    provider_version: str
    observable_type: str
    observable_value: str
    claim: IntelligenceClaim
    confidence_label: str
    summary: str
    retrieved_at: datetime
    data_timestamp: datetime | None = None
    expires_at: datetime | None = None
    source_reference: str | None = None
    raw_response_sha256: str | None = None
    origin: str = "manual"
    archived: bool = False

    @property
    def cache_state(self) -> str:
        if self.expires_at is None:
            return "No expiry"
        return "Fresh" if self.expires_at >= datetime.now(UTC) else "Expired"


def build_relationships(records: tuple[EvidenceRecord, ...]) -> RelationshipSnapshot:
    """Build a bounded, deterministic graph whose every edge cites evidence."""

    node_support: dict[tuple[EntityType, str], set[str]] = {}
    edge_support: dict[tuple[EntityId, EntityId, str, str, str], set[str]] = {}

    def node(kind: EntityType, value: str) -> EntityId:
        key = (kind, value)
        node_support.setdefault(key, set())
        return EntityId(f"entity-{_stable(kind.value, value)}")

    def edge(
        left: EntityId,
        right: EntityId,
        relation: str,
        rule: str,
        explanation: str,
        evidence_id: str,
    ) -> None:
        edge_support.setdefault((left, right, relation, rule, explanation), set()).add(evidence_id)

    for record in records:
        evidence_id = str(record.evidence_id)
        event = node(EntityType.EVENT, record.event_id)
        source = node(EntityType.SOURCE, record.source_name)
        node_support[(EntityType.EVENT, record.event_id)].add(evidence_id)
        node_support[(EntityType.SOURCE, record.source_name)].add(evidence_id)
        edge(
            source,
            event,
            "contains",
            "REL-SOURCE-EVENT-1",
            "The selected source contains this canonical event.",
            evidence_id,
        )

        host_id: EntityId | None = None
        if record.host_name:
            host_id = node(EntityType.HOST, record.host_name)
            node_support[(EntityType.HOST, record.host_name)].add(evidence_id)
            edge(
                event,
                host_id,
                "observed on",
                "REL-EVENT-HOST-1",
                "The event declares this host.",
                evidence_id,
            )
        if record.user_name:
            user = node(EntityType.USER, record.user_name)
            node_support[(EntityType.USER, record.user_name)].add(evidence_id)
            edge(
                event,
                user,
                "associated with",
                "REL-EVENT-USER-1",
                "The event declares this user.",
                evidence_id,
            )

        typed: dict[EntityType, list[EntityId]] = {}
        for observable in record.observables:
            try:
                kind = EntityType(observable.kind)
            except ValueError:
                kind = EntityType.OBSERVABLE
            observable_id = node(kind, observable.canonical)
            typed.setdefault(kind, []).append(observable_id)
            node_support[(kind, observable.canonical)].add(evidence_id)
            edge(
                event,
                observable_id,
                "references",
                "REL-EVENT-OBS-1",
                f"Canonical field {observable.field_path} contains this observable.",
                evidence_id,
            )
            if host_id is not None and kind in {
                EntityType.IPV4,
                EntityType.DOMAIN,
                EntityType.SHA256,
            }:
                relation = {
                    EntityType.IPV4: "connected to",
                    EntityType.DOMAIN: "queried",
                    EntityType.SHA256: "observed hash",
                }[kind]
                edge(
                    host_id,
                    observable_id,
                    relation,
                    "REL-HOST-OBS-1",
                    "The host and observable occur in the same source event.",
                    evidence_id,
                )

        is_dns = "dns" in f"{record.category} {record.action}".casefold()
        if is_dns:
            for domain_id in typed.get(EntityType.DOMAIN, []):
                for ip_id in typed.get(EntityType.IPV4, []):
                    edge(
                        domain_id,
                        ip_id,
                        "resolved to",
                        "REL-DNS-ANSWER-1",
                        "The domain and IPv4 address occur in the same DNS event.",
                        evidence_id,
                    )

    nodes = tuple(
        RelationshipNode(
            entity_id=EntityId(f"entity-{_stable(kind.value, value)}"),
            entity_type=kind,
            value=value,
            label=value,
            evidence_ids=tuple(sorted(support)),
        )
        for (kind, value), support in sorted(
            node_support.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
    )
    edges = tuple(
        EvidenceRelationship(
            relationship_id=RelationshipId(
                f"relationship-{_stable(str(left), str(right), relation, rule)}"
            ),
            source_id=left,
            target_id=right,
            relation=relation,
            rule_id=rule,
            explanation=explanation,
            evidence_ids=tuple(sorted(support)),
        )
        for (left, right, relation, rule, explanation), support in sorted(
            edge_support.items(), key=lambda item: tuple(str(value) for value in item[0])
        )
    )
    return RelationshipSnapshot(nodes, edges)


def build_recommendations(
    analysis: AnalysisSnapshot | None,
    relationships: RelationshipSnapshot,
) -> tuple[Recommendation, ...]:
    """Generate transparent next actions from explicit coverage and graph rules."""

    values: list[Recommendation] = []

    def add(
        rule_id: str,
        priority: RecommendationPriority,
        category: str,
        title: str,
        rationale: str,
        expected: str,
        safety: str,
        action: str,
        *,
        evidence_ids: tuple[str, ...] = (),
        coverage_ids: tuple[str, ...] = (),
        relationship_ids: tuple[str, ...] = (),
    ) -> None:
        values.append(
            Recommendation(
                recommendation_id=RecommendationId(
                    f"recommendation-{_stable(rule_id, *evidence_ids, *coverage_ids, *relationship_ids)}"
                ),
                rule_id=rule_id,
                rule_version="1.0.0",
                priority=priority,
                category=category,
                title=title,
                rationale=rationale,
                expected_value=expected,
                safety_note=safety,
                action=action,
                evidence_ids=evidence_ids,
                coverage_cell_ids=coverage_ids,
                relationship_ids=relationship_ids,
            )
        )

    if analysis is not None:
        for cell in analysis.coverage:
            cid = (str(cell.cell_id),)
            if cell.state is CoverageState.PARTIAL_COVERAGE:
                add(
                    "REC-COVERAGE-PARTIAL",
                    RecommendationPriority.IMMEDIATE,
                    "Coverage",
                    f"Complete partial telemetry for {cell.step_label}",
                    cell.reason.message,
                    "Reduce the blind spot before drawing a conclusion.",
                    "Preserve the original source and document every retry.",
                    cell.reason.recovery
                    or "Re-export the source with the required fields and import it again.",
                    coverage_ids=cid,
                    evidence_ids=tuple(str(value) for value in cell.evidence_ids),
                )
            elif cell.state is CoverageState.SOURCE_FAILED:
                add(
                    "REC-SOURCE-FAILED",
                    RecommendationPriority.IMMEDIATE,
                    "Acquisition",
                    f"Recover failed source for {cell.step_label}",
                    cell.reason.message,
                    "Restore a missing search lane.",
                    "Do not overwrite the failed source; retain its diagnostic.",
                    cell.reason.recovery or "Acquire a fresh copy and retry.",
                    coverage_ids=cid,
                )
            elif cell.state is CoverageState.FORMAT_UNSUPPORTED:
                add(
                    "REC-FORMAT-UNSUPPORTED",
                    RecommendationPriority.USEFUL,
                    "Ingestion",
                    f"Map unsupported telemetry for {cell.step_label}",
                    cell.reason.message,
                    "Make the source searchable without altering the original.",
                    "Use an explicit sidecar mapping and verify both file hashes.",
                    cell.reason.recovery or "Convert or map the source, then preview it again.",
                    coverage_ids=cid,
                )
            elif cell.state is CoverageState.SOURCE_NOT_PROVIDED:
                add(
                    "REC-SOURCE-MISSING",
                    RecommendationPriority.USEFUL,
                    "Acquisition",
                    f"Acquire {cell.telemetry} telemetry",
                    cell.reason.message,
                    "Determine whether the IOC appears in an unsearched data source.",
                    "Match the requested collection period to the incident window.",
                    cell.reason.recovery
                    or f"Collect {cell.telemetry} data for the scoped systems.",
                    coverage_ids=cid,
                )

        if analysis.sightings:
            evidence_ids = tuple(sorted({str(value.evidence_id) for value in analysis.sightings}))
            add(
                "REC-PRESERVE-DIRECT",
                RecommendationPriority.IMMEDIATE,
                "Preservation",
                "Preserve and review direct-match records",
                f"The deterministic recipe produced {len(analysis.sightings)} exact sighting(s).",
                "Protect the strongest current lead evidence and validate its surrounding context.",
                "A direct match is not proof of compromise; validate provenance and context.",
                "Open the cited evidence, review adjacent events, then export a verified Case Capsule.",
                evidence_ids=evidence_ids,
            )

    dns_edges = tuple(edge for edge in relationships.edges if edge.relation == "resolved to")
    if dns_edges:
        add(
            "REC-DNS-PIVOT",
            RecommendationPriority.USEFUL,
            "Pivot",
            "Pivot across DNS resolutions",
            f"The evidence graph contains {len(dns_edges)} domain-to-IP resolution relationship(s).",
            "Test whether related infrastructure appears elsewhere in the scoped evidence.",
            "Keep the pivot bounded to the case; do not resolve domains over the network in Offline mode.",
            "Open each cited relationship and filter Evidence by its domain and IP values.",
            evidence_ids=tuple(sorted({item for edge in dns_edges for item in edge.evidence_ids})),
            relationship_ids=tuple(str(edge.relationship_id) for edge in dns_edges),
        )

    if not values:
        add(
            "REC-IMPORT-EVIDENCE",
            RecommendationPriority.IMMEDIATE,
            "Workflow",
            "Import and analyze evidence",
            "No completed analysis is available for recommendation rules.",
            "Enable evidence-backed actions and coverage diagnostics.",
            "Preview sources before import and preserve their digests.",
            "Open Evidence, import supported sources, then run the IOC analysis.",
        )
    order = {
        RecommendationPriority.IMMEDIATE: 0,
        RecommendationPriority.USEFUL: 1,
        RecommendationPriority.OPTIONAL: 2,
    }
    return tuple(
        sorted(values, key=lambda value: (order[value.priority], value.category, value.title))
    )


def intelligence_conflicts(
    assertions: tuple[IntelligenceAssertion, ...],
) -> frozenset[AssertionId]:
    """Return active assertion IDs whose observable has incompatible claims."""

    groups: dict[tuple[str, str], dict[IntelligenceClaim, list[AssertionId]]] = {}
    for assertion in assertions:
        if assertion.archived:
            continue
        groups.setdefault((assertion.observable_type, assertion.observable_value), {}).setdefault(
            assertion.claim, []
        ).append(assertion.assertion_id)
    conflicting: set[AssertionId] = set()
    for claims in groups.values():
        decisive = {
            claim
            for claim in claims
            if claim not in {IntelligenceClaim.UNKNOWN, IntelligenceClaim.CONTEXT}
        }
        if len(decisive) > 1:
            for claim in decisive:
                conflicting.update(claims[claim])
    return frozenset(conflicting)


def _stable(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
