"""Validated, canonical IOC values used by every future search recipe."""

import ipaddress
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

from ioc_evidence_packager.domain.errors import ValidationError

ObservableId = NewType("ObservableId", str)

SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
DOMAIN_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class ObservableType(StrEnum):
    """Observable types supported by the Slice 2 lead validator."""

    IPV4 = "ipv4"
    DOMAIN = "domain"
    SHA256 = "sha256"


@dataclass(frozen=True, slots=True)
class Observable:
    """Case observable preserving both analyst input and comparison value."""

    observable_id: ObservableId
    observable_type: ObservableType
    original_value: str
    canonical_value: str
    role: str = "lead"


@dataclass(frozen=True, slots=True)
class ParsedObservable:
    """Validated observable before it receives a case-local identifier."""

    observable_type: ObservableType
    original_value: str
    canonical_value: str


def parse_observable(value: str) -> ParsedObservable:
    """Detect and canonicalize an IPv4 address, domain, or SHA-256 hash."""

    original = value.strip()
    if not original:
        raise ValidationError("Enter an IPv4 address, domain, or SHA-256 hash.")
    if any(character.isspace() for character in original):
        raise ValidationError("An observable cannot contain whitespace.")

    hash_candidate = original.removeprefix("sha256:").removeprefix("SHA256:")
    if SHA256_PATTERN.fullmatch(hash_candidate):
        return ParsedObservable(
            observable_type=ObservableType.SHA256,
            original_value=original,
            canonical_value=hash_candidate.lower(),
        )
    if _looks_like_hash(hash_candidate):
        raise ValidationError("A SHA-256 value must contain exactly 64 hexadecimal characters.")

    try:
        address = ipaddress.ip_address(original)
    except ValueError:
        return _parse_domain(original)
    if isinstance(address, ipaddress.IPv4Address):
        return ParsedObservable(
            observable_type=ObservableType.IPV4,
            original_value=original,
            canonical_value=str(address),
        )
    raise ValidationError("IPv6 lead validation is scheduled after the first three recipes.")


def _parse_domain(original: str) -> ParsedObservable:
    candidate = original[:-1] if original.endswith(".") else original
    if not candidate or ".." in candidate:
        raise ValidationError("The domain contains an empty label.")

    try:
        canonical = candidate.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValidationError("The domain contains an invalid internationalized label.") from error

    labels = canonical.split(".")
    if len(labels) < 2:
        raise ValidationError("Enter a fully qualified domain with at least two labels.")
    if len(canonical) > 253:
        raise ValidationError("The canonical domain must be 253 characters or fewer.")
    if any(DOMAIN_LABEL_PATTERN.fullmatch(label) is None for label in labels):
        raise ValidationError(
            "Domain labels may contain letters, digits, and interior hyphens only."
        )
    if labels[-1].isdigit():
        raise ValidationError("The final domain label cannot contain only digits.")

    return ParsedObservable(
        observable_type=ObservableType.DOMAIN,
        original_value=original,
        canonical_value=canonical,
    )


def _looks_like_hash(value: str) -> bool:
    return 24 <= len(value) <= 128 and all(
        character in "0123456789abcdefABCDEF" for character in value
    )
