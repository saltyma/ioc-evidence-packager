"""Render the canonical SVG app icon into packaged PNG and ICO assets."""

from argparse import ArgumentParser
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QImageWriter, QPainter
from PySide6.QtSvg import QSvgRenderer


def render(svg_path: Path, output_path: Path, size: int, image_format: bytes) -> None:
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG asset: {svg_path}")

    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(Qt.GlobalColor.transparent))
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, size, size))
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
    parser.add_argument("svg", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    app = QGuiApplication([])
    render(args.svg, args.output_directory / "app-icon-256.png", 256, b"png")
    render(args.svg, args.output_directory / "app-icon.ico", 256, b"ico")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
