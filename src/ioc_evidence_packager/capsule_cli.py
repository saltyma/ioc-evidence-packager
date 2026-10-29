"""Independent verification and PDF/ZIP projection command."""

import argparse
from pathlib import Path

from ioc_evidence_packager.reporting.capsule import verify_capsule
from ioc_evidence_packager.reporting.projections import project_capsule


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or project an IOC Case Capsule offline")
    parser.add_argument("capsule", type=Path)
    parser.add_argument("--format", choices=("verify", "pdf", "zip"), default="verify")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.format == "verify":
        result = verify_capsule(args.capsule)
        print("\n".join(result.messages))
        return 0 if result.valid else 1
    if args.output is None:
        parser.error("--output is required for PDF or ZIP")
    print(project_capsule(args.capsule, args.output, args.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
