"""Versioned structured IOC search recipes."""

from dataclasses import dataclass

from ioc_evidence_packager.domain.observables import ObservableType


@dataclass(frozen=True, slots=True)
class RecipeStep:
    """One expected telemetry capability in an IOC recipe."""

    step_id: str
    label: str
    telemetry: str
    field_prefixes: tuple[str, ...]

    def supports(self, field_path: str) -> bool:
        return any(
            field_path == prefix
            or field_path.startswith(f"{prefix}.")
            or field_path.startswith(f"{prefix}[")
            for prefix in self.field_prefixes
        )


@dataclass(frozen=True, slots=True)
class SearchRecipe:
    """Exact-match rules and coverage expectations for one lead type."""

    recipe_id: str
    version: str
    observable_type: ObservableType
    rule_id: str
    steps: tuple[RecipeStep, ...]

    def step_for(self, field_path: str) -> RecipeStep | None:
        return next((step for step in self.steps if step.supports(field_path)), None)


IPV4_RECIPE = SearchRecipe(
    recipe_id="ipv4",
    version="1.0.0",
    observable_type=ObservableType.IPV4,
    rule_id="ipv4.direct.exact",
    steps=(
        RecipeStep("dns_resolution", "DNS resolution", "DNS", ("dns",)),
        RecipeStep("network_endpoint", "Network endpoint", "Network", ("network", "tls")),
        RecipeStep(
            "authentication_origin",
            "Authentication origin",
            "Authentication",
            ("authentication",),
        ),
    ),
)

DOMAIN_RECIPE = SearchRecipe(
    recipe_id="domain",
    version="1.0.0",
    observable_type=ObservableType.DOMAIN,
    rule_id="domain.direct.exact",
    steps=(
        RecipeStep("dns_query", "DNS query", "DNS", ("dns",)),
        RecipeStep("tls_server_name", "TLS server name", "Network", ("tls", "http")),
        RecipeStep(
            "process_reference",
            "Process or command reference",
            "Endpoint",
            ("process",),
        ),
    ),
)

SHA256_RECIPE = SearchRecipe(
    recipe_id="sha256",
    version="1.0.0",
    observable_type=ObservableType.SHA256,
    rule_id="sha256.direct.exact",
    steps=(
        RecipeStep("file_hash", "File SHA-256", "Endpoint", ("file",)),
        RecipeStep("process_image_hash", "Process image SHA-256", "Process", ("process",)),
    ),
)

RECIPES = {recipe.observable_type: recipe for recipe in (IPV4_RECIPE, DOMAIN_RECIPE, SHA256_RECIPE)}


def recipe_for(observable_type: ObservableType) -> SearchRecipe:
    """Return the supported recipe for a validated lead type."""

    return RECIPES[observable_type]
