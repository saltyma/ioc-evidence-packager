"""Typed application preferences backed by the operating system's Qt settings store."""

from dataclasses import dataclass

from PySide6.QtCore import QSettings


@dataclass(frozen=True, slots=True)
class DesktopPreferences:
    density: str = "Comfortable"
    detail_width: int = 760
    high_contrast: bool = True
    virustotal_enabled: bool = False
    cache_hours: int = 24
    confirm_external_links: bool = True
    default_privacy_mode: str = "offline"


class DesktopSettingsStore:
    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings()

    def load(self) -> DesktopPreferences:
        return DesktopPreferences(
            density=str(self._settings.value("appearance/density", "Comfortable")),
            detail_width=_integer(
                self._settings.value("appearance/detail_width", 760), 760, 620, 900
            ),
            high_contrast=_boolean(self._settings.value("appearance/high_contrast", True)),
            virustotal_enabled=_boolean(
                self._settings.value("intelligence/virustotal_enabled", False)
            ),
            cache_hours=_integer(self._settings.value("intelligence/cache_hours", 24), 24, 1, 168),
            confirm_external_links=_boolean(
                self._settings.value("privacy/confirm_external_links", True)
            ),
            default_privacy_mode=str(self._settings.value("privacy/default_mode", "offline")),
        )

    def save(self, value: DesktopPreferences) -> None:
        self._settings.setValue("appearance/density", value.density)
        self._settings.setValue("appearance/detail_width", value.detail_width)
        self._settings.setValue("appearance/high_contrast", value.high_contrast)
        self._settings.setValue("intelligence/virustotal_enabled", value.virustotal_enabled)
        self._settings.setValue("intelligence/cache_hours", value.cache_hours)
        self._settings.setValue("privacy/confirm_external_links", value.confirm_external_links)
        self._settings.setValue("privacy/default_mode", value.default_privacy_mode)
        self._settings.sync()

    def reset(self) -> DesktopPreferences:
        for group in ("appearance", "intelligence", "privacy"):
            self._settings.beginGroup(group)
            self._settings.remove("")
            self._settings.endGroup()
        self._settings.sync()
        return DesktopPreferences()


def _boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).casefold() in {"1", "true", "yes", "on"}


def _integer(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value))
    except ValueError:
        parsed = default
    return max(minimum, min(maximum, parsed))
