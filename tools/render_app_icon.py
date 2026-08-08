"""Crop the canonical raster artwork into packaged PNG and ICO assets."""

from argparse import ArgumentParser
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QImageReader,
    QImageWriter,
    QPainter,
    QPainterPath,
)

ICON_CROP_RATIO = 0.82


def _load_square_crop(source_path: Path) -> QImage:
    reader = QImageReader(str(source_path))
    reader.setAutoTransform(True)
    source = reader.read()
    if source.isNull():
        raise RuntimeError(f"Could not read icon artwork: {reader.errorString()}")
    side = max(1, round(min(source.width(), source.height()) * ICON_CROP_RATIO))
    left = (source.width() - side) // 2
    top = (source.height() - side) // 2
    return source.copy(QRect(left, top, side, side))


def render(source: QImage, output_path: Path, size: int, image_format: bytes) -> None:
    """Render a rounded square icon at one target size."""

    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(Qt.GlobalColor.transparent))
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        bounds = QRectF(1, 1, size - 2, size - 2)
        clip = QPainterPath()
        clip.addRoundedRect(bounds, size * 0.12, size * 0.12)
        painter.setClipPath(clip)
        painter.drawImage(bounds, source)
    finally:
        painter.end()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = QImageWriter(str(output_path), image_format)
    writer.setQuality(100)
    if image_format == b"png":
        writer.setCompression(9)
    if not writer.write(image):
        raise RuntimeError(f"Could not write {output_path}: {writer.errorString()}")


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--docs-preview", type=Path)
    args = parser.parse_args()

    app = QGuiApplication([])
    source = _load_square_crop(args.source)
    render(source, args.output_directory / "app-icon-256.png", 256, b"png")
    render(source, args.output_directory / "app-icon.ico", 256, b"ico")
    if args.docs_preview is not None:
        render(source, args.docs_preview, 512, b"png")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
