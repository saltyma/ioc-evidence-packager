"""Observable validation and canonicalization tests."""

import pytest

from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.domain.observables import ObservableType, parse_observable


@pytest.mark.parametrize(
    ("value", "observable_type", "canonical"),
    [
        ("203.0.113.42", ObservableType.IPV4, "203.0.113.42"),
        ("Example.TEST.", ObservableType.DOMAIN, "example.test"),
        ("täst.example", ObservableType.DOMAIN, "xn--tst-qla.example"),
        ("A" * 64, ObservableType.SHA256, "a" * 64),
        ("sha256:" + "B" * 64, ObservableType.SHA256, "b" * 64),
    ],
)
def test_supported_observables_preserve_input_and_canonicalize(
    value: str,
    observable_type: ObservableType,
    canonical: str,
) -> None:
    parsed = parse_observable(f"  {value}  ")

    assert parsed.observable_type is observable_type
    assert parsed.original_value == value
    assert parsed.canonical_value == canonical


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "Enter an IPv4"),
        ("example", "fully qualified"),
        ("bad_domain.example", "Domain labels"),
        ("2001:db8::1", "IPv6"),
        ("a" * 63, "exactly 64"),
        ("example.123", "final domain label"),
    ],
)
def test_unsupported_or_ambiguous_values_are_rejected(value: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_observable(value)
