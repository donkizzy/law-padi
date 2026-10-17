"""Identify the packaged sources without including local secrets or build output."""

import hashlib
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    paths = [
        path
        for folder in (
            root / "backend/app",
            root / "frontend/src",
            root / "frontend/public",
        )
        for path in folder.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not path.name.endswith(".test.ts")
        and root / "backend/app/frontend" not in path.parents
        and (
            root / "frontend/public" in path.parents
            or path.suffix
            in {
                ".py",
                ".json",
                ".ts",
                ".tsx",
                ".css",
                ".svg",
                ".png",
                ".ico",
                ".webmanifest",
            }
        )
    ]
    paths.extend(
        root / name
        for name in (
            "bun.lock",
            "uv.lock",
            "package.json",
            "backend/pyproject.toml",
            "backend/Dockerfile",
            "frontend/package.json",
            "frontend/vite.config.ts",
            "frontend/index.html",
            "docs/plain-language-retrieval-benchmark-v1.json",
            "backend/scripts/start-cloud-run.sh",
            "deployment/cloudflare/worker.ts",
            "deployment/cloudflare/public-pages.ts",
            "deployment/cloudflare/wrangler.json",
            "deployment/cloudflare/tsconfig.json",
            "deployment/render/Dockerfile",
            "deployment/render/start.sh",
            ".dockerignore",
        )
    )
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    print(f"source-{digest.hexdigest()[:16]}")  # noqa: T201


if __name__ == "__main__":
    main()
