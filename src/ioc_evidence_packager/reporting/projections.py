"""Offline PDF and ZIP projections of an already verified capsule."""

import json
import os
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.reporting.capsule import verify_capsule


def project_capsule(source: Path, destination: Path, kind: str) -> Path:
    """Create an optional sidecar without changing the capsule or overwriting files."""
    result = verify_capsule(source)
    if not result.valid:
        raise ValidationError("Verify the capsule successfully before creating a projection.")
    if kind not in {"pdf", "zip"}:
        raise ValidationError("Choose PDF or ZIP.")
    target = destination.resolve()
    if target.exists() or source.resolve() in target.parents:
        raise ValidationError("Choose a new file outside the verified capsule directory.")
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".projection-")
    os.close(handle)
    stage = Path(temporary)
    try:
        if kind == "zip":
            with ZipFile(stage, "w", ZIP_DEFLATED) as archive:
                for file in sorted(source.iterdir()):
                    if not file.is_file() or file.is_symlink():
                        raise ValidationError("Only regular capsule files can be archived.")
                    archive.write(file, file.name)
            with ZipFile(stage) as archive:
                if archive.testzip() is not None:
                    raise ValidationError("ZIP integrity check failed.")
        else:
            _pdf(source, stage)
        # Exclusive creation also protects against a competing destination writer.
        with target.open("xb") as output, stage.open("rb") as input_file:
            while chunk := input_file.read(1024 * 1024):
                output.write(chunk)
    finally:
        stage.unlink(missing_ok=True)
    return target


def _pdf(source: Path, destination: Path) -> None:
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    styles["Heading1"].textColor = colors.HexColor("#43315e")
    story = []

    def paragraph(text: str, style: str = "BodyText") -> None:
        story.append(Paragraph(escape(text), styles[style]))
        story.append(Spacer(1, 6))

    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    paragraph("IOC investigation handoff", "Title")
    paragraph(
        "Print projection of a verified Case Capsule. Verify manifest.json in the original "
        "directory for machine-readable evidence and integrity checks."
    )
    paragraph(f"Profile: {manifest['export_profile']} | Exported: {manifest['created_at']}")
    paragraph("Scope and limitations", "Heading1")
    paragraph(str(manifest.get("requested_window", "No requested time bounds")))
    paragraph(str(manifest.get("selection", "Complete exported evidence set")))
    coverage = json.loads((source / "coverage.json").read_text(encoding="utf-8"))
    for cell in coverage["cells"]:
        paragraph(f"{cell['step_label']}: {cell['state']}", "Heading2")
        paragraph(cell["reason"]["message"])
    paragraph("Evidence ledger", "Heading1")
    for line in (source / "evidence.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        paragraph(
            f"{record['occurred_at'] or 'Undated'} | {record['classification']} | "
            f"{record['event_id']}",
            "Heading2",
        )
        paragraph(
            f"{record['category']} / {record['action']} | {record['host']} | {record['user']}"
        )
        paragraph(
            "Observables: "
            + "; ".join(f"{v['kind']}: {v['canonical']}" for v in record["observables"])
        )
        provenance = record["provenance"]
        paragraph(
            f"Source: {provenance['source_name']} | position: {provenance['physical_line']} | "
            f"SHA-256: {provenance['source_sha256']}"
        )
        if record.get("analyst_review"):
            paragraph("Analyst note: " + record["analyst_review"]["note"])
    for filename, title in (
        ("recommendations.json", "Recommended actions"),
        ("intelligence.json", "Intelligence claims"),
    ):
        paragraph(title, "Heading1")
        document = json.loads((source / filename).read_text(encoding="utf-8"))
        paragraph(json.dumps(document, ensure_ascii=True, indent=2))
    SimpleDocTemplate(str(destination), pagesize=A4, title="IOC investigation handoff").build(story)
