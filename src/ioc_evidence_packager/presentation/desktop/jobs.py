"""Qt worker adapters for bounded background source preview."""

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ioc_evidence_packager.ingestion import SourceInspectionService


class SourcePreviewSignals(QObject):
    """Queued worker outcomes delivered safely to the GUI thread."""

    completed = Signal(str, object)
    failed = Signal(str, str)


class SourcePreviewWorker(QRunnable):
    """Hash and probe one source away from the Qt event loop."""

    def __init__(self, service: SourceInspectionService, path: Path) -> None:
        super().__init__()
        self._service = service
        self._path = path
        self.signals = SourcePreviewSignals()

    @Slot()
    def run(self) -> None:
        try:
            preview = self._service.inspect(self._path)
        except Exception as error:  # noqa: BLE001 - keep worker failures out of the Qt loop
            self.signals.failed.emit(str(self._path), str(error))
            return
        self.signals.completed.emit(str(self._path), preview)
