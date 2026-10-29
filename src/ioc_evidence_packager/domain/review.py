"""Analyst metadata stored separately from source facts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceReview:
    bookmarked: bool = False
    note: str = ""
    included: bool = True
