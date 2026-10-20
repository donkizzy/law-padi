"""Offline, resumable OCR of approved PDFs; output always requires review.

Run in the existing OCR worker image with networking disabled. This command
does not access the database, verify sources, or create canonical provisions.
"""

import argparse
import csv
import hashlib
import io
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

VERSION = "statute-review-lines-v1"


def decode_tsv(output: str, page_number: int) -> dict[str, Any]:
    lines: dict[tuple[str, ...], list[str]] = {}
    spans: list[dict[str, Any]] = []
    for row in csv.DictReader(
        io.StringIO(output), delimiter="\t", quoting=csv.QUOTE_NONE
    ):
        value = (row.get("text") or "").strip()
        confidence = float(row.get("conf") or "-1") / 100
        if not value or confidence < 0:
            continue
        key = tuple(
            row.get(name) or "" for name in ("block_num", "par_num", "line_num")
        )
        lines.setdefault(key, []).append(value)
        left, top, width, height = (
            float(row.get(name) or 0) for name in ("left", "top", "width", "height")
        )
        spans.append(
            {
                "text": value,
                "bbox": {"x0": left, "y0": top, "x1": left + width, "y1": top + height},
                "confidence": confidence,
                "reading_order": len(spans) + 1,
            }
        )
    return {
        "page_number": page_number,
        "text": "\n".join(" ".join(words) for words in lines.values()),
        "spans": spans,
        "confidence": round(
            sum(span["confidence"] for span in spans) / max(len(spans), 1), 4
        ),
        "method": "local_ocr",
        "provider_version": VERSION,
        "review_status": "needs_review",
    }


def extract_page(pdf: Path, page: int, dpi: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="statute-review-") as directory:
        image = Path(directory) / "page"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page),
                "-l",
                str(page),
                "-r",
                str(dpi),
                "-singlefile",
                "-png",
                str(pdf),
                str(image),
            ],
            check=True,
            capture_output=True,
            timeout=90,
        )
        completed = subprocess.run(
            [
                "tesseract",
                str(image.with_suffix(".png")),
                "stdout",
                "-l",
                "eng",
                "--psm",
                "6",
                "tsv",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        result = decode_tsv(completed.stdout, page)
        result["coordinate_space"] = {"unit": "raster_pixels", "render_dpi": dpi}
        return result


def save_pages(
    destination: Path, identity: dict[str, Any], pages: dict[int, dict[str, Any]]
) -> None:
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                **identity,
                "review_status": "needs_review",
                "pages": sorted(pages.values(), key=lambda item: item["page_number"]),
            },
            indent=2,
        )
        + "\n"
    )
    temporary.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--dpi", type=int, choices=(150, 200, 300), default=200)
    parser.add_argument("--previews-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    for source in manifest["sources"]:
        if source.get("download_approved") is not True:
            raise ValueError("PDF download approval is required")
        folder = (args.source_root / source["instrument_slug"]).resolve()
        pdf = (folder / source["filename"]).resolve()
        if args.source_root.resolve() not in pdf.parents:
            raise ValueError("Source must be inside the review folder")
        content = pdf.read_bytes()
        if (
            hashlib.sha256(content).hexdigest() != source["sha256"]
            or len(content) != source["size_bytes"]
        ):
            raise ValueError(
                "Retained source hash/size differs from the approved manifest"
            )
        if args.previews_only:
            previews = folder / "review-previews"
            previews.mkdir(exist_ok=True)
            subprocess.run(
                [
                    "pdftoppm",
                    "-scale-to",
                    "1000",
                    "-png",
                    str(pdf),
                    str(previews / "page"),
                ],
                check=True,
                capture_output=True,
                timeout=300,
            )
            continue
        destination = folder / "ocr-layout-pages-v2.json"
        identity = {
            "source_sha256": source["sha256"],
            "version": VERSION,
            "dpi": args.dpi,
        }
        existing = json.loads(destination.read_text()) if destination.exists() else {}
        pages = (
            {page["page_number"]: page for page in existing.get("pages", [])}
            if all(existing.get(key) == value for key, value in identity.items())
            else {}
        )

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [
                executor.submit(extract_page, pdf, page, args.dpi)
                for page in range(1, source["page_count"] + 1)
                if page not in pages
            ]
            for future in as_completed(futures):
                result = future.result()
                pages[result["page_number"]] = result
                if len(pages) % 20 == 0 or len(pages) == source["page_count"]:
                    save_pages(destination, identity, pages)
                    print(  # noqa: T201
                        f"{source['instrument_slug']}: {len(pages)}/{source['page_count']} pages retained for review",
                        flush=True,
                    )
        save_pages(destination, identity, pages)


if __name__ == "__main__":
    main()
