#!/usr/bin/env python3
# ruff: noqa: T201 -- This operator CLI deliberately reports non-secret status.
"""Explicit, reproducible free-tier deployment commands; never reads .env.

Use `validate` without cloud credentials. Every cloud command passes the project
and region explicitly, and no command links billing or buys provider credits.
"""

import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
REGIONS = {"us-east1", "us-central1", "us-west1"}
REGISTRY_LIMIT = 512 * 1024 * 1024
PER_IMAGE_TARGET = 240 * 1024 * 1024
SECRET_PATH = "/run/secrets/runtime.env"


def run(
    argv: list[str],
    *,
    capture: bool = False,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        argv,
        cwd=ROOT,
        check=check,
        text=True,
        env=env,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def exists(argv: list[str]) -> bool:
    return (
        subprocess.run(
            argv,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def validate_config(config: dict) -> None:
    for key in (
        "project_id",
        "image_repository",
        "api_service",
        "handler_service",
        "queue_name",
        "api_secret",
        "handler_secret",
        "cloudflare_worker_name",
    ):
        if not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", config.get(key, "")):
            raise ValueError(f"Invalid {key}")
    if config.get("region") not in REGIONS:
        raise ValueError(
            "Use us-east1, us-central1 or us-west1 for the backup storage allowance"
        )
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,221}", config.get("backup_bucket", "")):
        raise ValueError("Invalid backup_bucket")
    frontend = urlparse(config.get("frontend_url", ""))
    if (
        frontend.scheme != "https"
        or not frontend.hostname
        or not re.fullmatch(r"[a-z0-9.-]+", frontend.hostname)
        or frontend.port is not None
        or frontend.path not in {"", "/"}
        or frontend.query
        or frontend.fragment
        or frontend.username is not None
    ):
        raise ValueError("frontend_url must be one HTTPS origin")
    for key in ("api_secret_version", "handler_secret_version"):
        if not str(config.get(key, "")).isdigit():
            raise ValueError(f"{key} must pin a numbered Secret Manager version")
    account_id = config.get("cloudflare_account_id")
    if account_id is not None and not re.fullmatch(r"[a-f0-9]{32}", account_id):
        raise ValueError("cloudflare_account_id must be a 32-character account ID")


def gcloud(config: dict, *args: str) -> list[str]:
    return ["gcloud", *args, f"--project={config['project_id']}", "--quiet"]


def service_account(config: dict, role: str) -> str:
    return f"law-padi-{role}@{config['project_id']}.iam.gserviceaccount.com"


def image_name(config: dict, revision: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,62}", revision):
        raise ValueError("Revision must be a lowercase build identifier")
    return f"{config['region']}-docker.pkg.dev/{config['project_id']}/{config['image_repository']}/app:{revision}"


def runtime_env(
    config: dict, role: str, *, handler_url: str = "", generation: bool = False
) -> dict[str, str]:
    values = {
        "APP_RUNTIME_ROLE": role,
        "APP_RUNTIME_ENV_FILE": SECRET_PATH,
        "SERVE_FRONTEND": "false",
        "FRONTEND_HOST": config["frontend_url"].rstrip("/"),
        "CHAT_ENABLED": "true",
        "CHAT_GENERATION_ENABLED": str(generation).lower(),
        "CHAT_GENERATION_KILL_SWITCH": str(not generation).lower(),
        "CHAT_PROVIDER_CAPACITY_APPROVED": str(generation).lower(),
        "CHAT_MAX_ACTIVE_GENERATIONS": "1",
        "CHAT_WORKER_CONCURRENCY": "1",
        "DATABASE_POOL_SIZE": "5" if role == "api" else "2",
        "DATABASE_CONNECT_TIMEOUT_SECONDS": "15",
        "DATABASE_STATEMENT_TIMEOUT_MS": "30000",
        "DATABASE_LOCK_TIMEOUT_MS": "5000",
        "CHAT_DAILY_BUDGET_USD": "0.12",
        "CHAT_MONTHLY_BUDGET_USD": "4",
        "AI_MONTHLY_BUDGET_USD": "5",
        "EMBEDDING_QUERY_ENABLED": "false",
        "CHAT_GUEST_DAILY_LIMIT": "3",
        "CHAT_ACCOUNT_DAILY_LIMIT": "10",
        "CHAT_GUEST_BURST_LIMIT": "1",
        "CHAT_ACCOUNT_BURST_LIMIT": "2",
        "CHAT_DISPATCH_MODE": "cloud_tasks" if handler_url else "poll",
        "GCP_PROJECT_ID": config["project_id"],
        "GCP_TASKS_LOCATION": config["region"],
        "GCP_CHAT_QUEUE": config["queue_name"],
        "CHAT_TASK_SERVICE_ACCOUNT": service_account(config, "invoker"),
        "CHAT_TASK_DISPATCH_DEADLINE_SECONDS": "300",
        "CHAT_TASK_REDISPATCH_SECONDS": "600",
        "CHAT_TASK_RECONCILE_LIMIT": "20",
        "GCS_BACKUP_BUCKET": config["backup_bucket"],
    }
    if handler_url:
        values["CHAT_TASK_HANDLER_URL"] = handler_url
        values["CHAT_TASK_AUDIENCE"] = handler_url
    return values


def safeguard(config: dict) -> None:
    if config.get("spending_safeguards_confirmed") is not True:
        raise ValueError(
            "Configure billing alerts/spend safeguards and confirm recurring free-tier eligibility in project.json before cloud mutation"
        )


def preflight(config: dict) -> None:
    for tool in ("gcloud", "docker", "bun"):
        if not shutil.which(tool):
            raise ValueError(f"Install {tool} before deployment")
    run(["gcloud", "version"])
    run(
        gcloud(
            config, "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"
        )
    )
    billing = json.loads(
        run(
            gcloud(
                config,
                "billing",
                "projects",
                "describe",
                config["project_id"],
                "--format=json",
            ),
            capture=True,
        )
    )
    if not billing.get("billingEnabled"):
        raise ValueError(
            "Dedicated project needs an explicitly linked billing account; this script does not link one"
        )
    run(["docker", "info", "--format", "{{.OSType}}"])
    print(
        "Preflight complete. Billing enabled does not prove free-tier eligibility or a hard $0 cap."
    )


def provision(config: dict) -> None:
    safeguard(config)
    run(
        gcloud(
            config,
            "services",
            "enable",
            "run.googleapis.com",
            "cloudtasks.googleapis.com",
            "cloudscheduler.googleapis.com",
            "artifactregistry.googleapis.com",
            "secretmanager.googleapis.com",
            "storage.googleapis.com",
        )
    )
    for role in ("api", "worker", "invoker", "scheduler"):
        email = service_account(config, role)
        if not exists(gcloud(config, "iam", "service-accounts", "describe", email)):
            run(
                gcloud(
                    config,
                    "iam",
                    "service-accounts",
                    "create",
                    f"law-padi-{role}",
                    f"--display-name=Law Padi {role}",
                )
            )
    if not exists(
        gcloud(
            config,
            "artifacts",
            "repositories",
            "describe",
            config["image_repository"],
            f"--location={config['region']}",
        )
    ):
        run(
            gcloud(
                config,
                "artifacts",
                "repositories",
                "create",
                config["image_repository"],
                "--repository-format=docker",
                f"--location={config['region']}",
            )
        )
    if not exists(
        gcloud(
            config, "storage", "buckets", "describe", f"gs://{config['backup_bucket']}"
        )
    ):
        run(
            gcloud(
                config,
                "storage",
                "buckets",
                "create",
                f"gs://{config['backup_bucket']}",
                f"--location={config['region']}",
                "--default-storage-class=STANDARD",
                "--uniform-bucket-level-access",
                "--public-access-prevention",
            )
        )
    run(
        gcloud(
            config,
            "storage",
            "buckets",
            "add-iam-policy-binding",
            f"gs://{config['backup_bucket']}",
            f"--member=serviceAccount:{service_account(config, 'worker')}",
            "--role=roles/storage.objectAdmin",
        )
    )
    # Disable soft delete: retained deleted objects otherwise continue counting
    # toward billable storage beyond the seven-export retention target.
    run(
        gcloud(
            config,
            "storage",
            "buckets",
            "update",
            f"gs://{config['backup_bucket']}",
            "--clear-soft-delete",
        )
    )
    queue_command = (
        "update"
        if exists(
            gcloud(
                config,
                "tasks",
                "queues",
                "describe",
                config["queue_name"],
                f"--location={config['region']}",
            )
        )
        else "create"
    )
    run(
        gcloud(
            config,
            "tasks",
            "queues",
            queue_command,
            config["queue_name"],
            f"--location={config['region']}",
            "--max-concurrent-dispatches=1",
            "--max-dispatches-per-second=1",
            "--max-attempts=3",
            "--max-retry-duration=900s",
            "--min-backoff=30s",
            "--max-backoff=300s",
            "--max-doublings=3",
            "--log-sampling-ratio=0",
        )
    )
    for role in ("api", "worker"):
        run(
            gcloud(
                config,
                "tasks",
                "queues",
                "add-iam-policy-binding",
                config["queue_name"],
                f"--location={config['region']}",
                f"--member=serviceAccount:{service_account(config, role)}",
                "--role=roles/cloudtasks.enqueuer",
            )
        )
        run(
            gcloud(
                config,
                "iam",
                "service-accounts",
                "add-iam-policy-binding",
                service_account(config, "invoker"),
                f"--member=serviceAccount:{service_account(config, role)}",
                "--role=roles/iam.serviceAccountUser",
            )
        )
    for role, key in (("api", "api_secret"), ("worker", "handler_secret")):
        if not exists(gcloud(config, "secrets", "describe", config[key])):
            run(
                gcloud(
                    config,
                    "secrets",
                    "create",
                    config[key],
                    "--replication-policy=automatic",
                )
            )
        run(
            gcloud(
                config,
                "secrets",
                "add-iam-policy-binding",
                config[key],
                f"--member=serviceAccount:{service_account(config, role)}",
                "--role=roles/secretmanager.secretAccessor",
            )
        )
    print(
        "Base resources ready; secret values, database corpus, source blobs and billing safeguards still require verification."
    )


def upload_secrets(
    config: dict, api_env: Path, worker_env: Path, config_path: Path
) -> None:
    safeguard(config)
    for path in (api_env, worker_env):
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError(f"{path}: supply a private chmod 600 dotenv file")
    # Values flow directly from file to gcloud. Neither secret content nor access
    # tokens are written to command arguments or printed by this script.
    for key, path in (("api", api_env), ("handler", worker_env)):
        active = json.loads(
            run(
                gcloud(
                    config,
                    "secrets",
                    "versions",
                    "list",
                    config[f"{key}_secret"],
                    "--filter=state:ENABLED",
                    "--format=json",
                ),
                capture=True,
            )
        )
        if len(active) >= 3:
            raise ValueError(
                "Disable superseded enabled secret versions before adding a fourth version per bundle"
            )
        resource = run(
            gcloud(
                config,
                "secrets",
                "versions",
                "add",
                config[f"{key}_secret"],
                f"--data-file={path.resolve()}",
                "--format=value(name)",
            ),
            capture=True,
        )
        config[f"{key}_secret_version"] = resource.rsplit("/", 1)[-1]
        # Keep the successful pin if the second upload is interrupted.
        config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(
        "Uploaded two secret bundles and pinned their numbered versions in project.json."
    )


def uncompressed_layers(stream) -> int:
    """Count actual layer tar bytes in classic Docker and OCI save formats."""
    total = 0
    found = False
    with tarfile.open(fileobj=stream, mode="r|*") as saved:
        for member in saved:
            if not member.isfile():
                continue
            layer = saved.extractfile(member)
            assert layer is not None
            if layer.peek(2).startswith(b"\x1f\x8b"):
                found = True
                with gzip.GzipFile(fileobj=layer) as unpacked:
                    while chunk := unpacked.read(1024 * 1024):
                        total += len(chunk)
            elif member.name.endswith("/layer.tar"):
                found = True
                total += member.size
    # Drain trailing tar padding before waiting for the saving process.
    while stream.read(1024 * 1024):
        pass
    if not found:
        raise ValueError("Cannot determine uncompressed image layers")
    return total


def build(config: dict, revision: str) -> None:
    image = image_name(config, revision)
    run(
        [
            "docker",
            "buildx",
            "build",
            "--platform=linux/amd64",
            "--target=cloud-run",
            "--load",
            "--file=backend/Dockerfile",
            f"--build-arg=BUILD_REVISION={revision}",
            f"--tag={image}",
            ".",
        ]
    )
    reported_size = int(
        run(["docker", "image", "inspect", image, "--format={{.Size}}"], capture=True)
    )
    saved = subprocess.Popen(
        ["docker", "image", "save", image], stdout=subprocess.PIPE, cwd=ROOT
    )

    # Stream into a counting sink; no large archive or secret file is created.
    class Counter:
        count = 0

        def write(self, data: bytes) -> int:
            self.count += len(data)
            return len(data)

    counter = Counter()
    with gzip.GzipFile(fileobj=counter, mode="wb", mtime=0) as archive:
        assert saved.stdout is not None
        shutil.copyfileobj(saved.stdout, archive)
    if saved.wait() != 0:
        raise ValueError("docker image save failed")
    layers = subprocess.Popen(
        ["docker", "image", "save", image], stdout=subprocess.PIPE, cwd=ROOT
    )
    assert layers.stdout is not None
    try:
        uncompressed = uncompressed_layers(layers.stdout)
    except Exception:
        layers.kill()
        layers.wait()
        raise
    if layers.wait() != 0:
        raise ValueError("docker image save failed while measuring layers")
    report = {
        "image": image,
        "uncompressed_bytes": uncompressed,
        "docker_reported_image_bytes": reported_size,
        "estimated_compressed_archive_bytes": counter.count,
        "per_image_target_bytes": PER_IMAGE_TARGET,
        "registry_allowance_bytes": REGISTRY_LIMIT,
        "exact_registry_usage_verified": False,
    }
    (ROOT / "deployment" / "image.report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))
    if counter.count > PER_IMAGE_TARGET:
        raise ValueError(
            "Compressed estimate exceeds 240 MiB; optimize before pushing or explicitly revise the hosting budget"
        )


def push(config: dict, revision: str) -> None:
    safeguard(config)
    image = image_name(config, revision)
    report = json.loads((ROOT / "deployment" / "image.report.json").read_text())
    if (
        report["image"] != image
        or report["estimated_compressed_archive_bytes"] > PER_IMAGE_TARGET
    ):
        raise ValueError("Build and measure this exact image before pushing")
    repository = f"{config['region']}-docker.pkg.dev/{config['project_id']}/{config['image_repository']}"
    existing = json.loads(
        run(
            gcloud(
                config,
                "artifacts",
                "docker",
                "images",
                "list",
                repository,
                "--format=json",
            ),
            capture=True,
        )
    )
    retained_bytes = 0
    for item in existing:
        raw_size = item.get("imageSizeBytes", item.get("sizeBytes"))
        if raw_size is None:
            raise ValueError(
                "Cannot verify retained registry bytes; inspect repository storage before pushing"
            )
        retained_bytes += int(raw_size)
    if retained_bytes + report["estimated_compressed_archive_bytes"] > REGISTRY_LIMIT:
        raise ValueError(
            "Retained registry images plus this build exceed the free storage allowance; review/remove obsolete images first"
        )
    run(
        [
            "gcloud",
            "auth",
            "configure-docker",
            f"{config['region']}-docker.pkg.dev",
            "--quiet",
        ]
    )
    run(["docker", "push", image])
    run(
        gcloud(
            config,
            "artifacts",
            "docker",
            "images",
            "list",
            repository,
            "--format=table(package,version,imageSizeBytes)",
        )
    )


def deploy_service(
    config: dict,
    role: str,
    revision: str,
    handler_url: str = "",
    generation: bool = False,
) -> str:
    service = config["api_service"] if role == "api" else config["handler_service"]
    secret_key = "api" if role == "api" else "handler"
    values = runtime_env(config, role, handler_url=handler_url, generation=generation)
    run(
        gcloud(
            config,
            "run",
            "deploy",
            service,
            f"--image={image_name(config, revision)}",
            f"--region={config['region']}",
            f"--service-account={service_account(config, 'api' if role == 'api' else 'worker')}",
            "--min=0",
            "--min-instances=0",
            f"--max={2 if role == 'api' else 1}",
            f"--max-instances={2 if role == 'api' else 1}",
            "--cpu=1",
            "--memory=512Mi",
            f"--concurrency={8 if role == 'api' else 1}",
            "--timeout=300s",
            "--cpu-throttling",
            "--no-cpu-boost",
            "--ingress=all",
            "--no-allow-unauthenticated",
            "--invoker-iam-check",
            "--port=8080",
            f"--set-secrets={SECRET_PATH}={config[f'{secret_key}_secret']}:{config[f'{secret_key}_secret_version']}",
            "--set-env-vars="
            + ",".join(f"{key}={value}" for key, value in values.items()),
        )
    )
    return run(
        gcloud(
            config,
            "run",
            "services",
            "describe",
            service,
            f"--region={config['region']}",
            "--format=value(status.url)",
        ),
        capture=True,
    )


def stage(config: dict, revision: str) -> None:
    safeguard(config)
    # Bootstrap privately, then pin the returned canonical origin for Tasks.
    origin = deploy_service(config, "tasks", revision)
    deploy_service(config, "tasks", revision, handler_url=origin)
    for role in ("invoker", "scheduler"):
        run(
            gcloud(
                config,
                "run",
                "services",
                "add-iam-policy-binding",
                config["handler_service"],
                f"--region={config['region']}",
                f"--member=serviceAccount:{service_account(config, role)}",
                "--role=roles/run.invoker",
            )
        )
    api = deploy_service(config, "api", revision, handler_url=origin)
    print(
        f"Private stage API: {api}\nPrivate task handler: {origin}\nGeneration remains disabled."
    )


def check_prompt_evidence(
    dataset: Path, captures: Path, judgments: Path, revision: str | None = None
) -> None:
    source = (ROOT / "backend/app/chat/__init__.py").read_text()
    match = re.search(r'EXPLANATION_PROMPT_VERSION\s*=\s*"([^"]+)"', source)
    if not match:
        raise ValueError("Cannot determine current prompt version")
    cases = json.loads(dataset.read_text())["cases"]
    rows = [
        json.loads(line) for line in captures.read_text().splitlines() if line.strip()
    ]
    if (
        len(cases) < 200
        or len(rows) != len(cases)
        or {row["id"] for row in rows} != {case["id"] for case in cases}
    ):
        raise ValueError("Public AI needs complete captures for the 200-case dataset")
    for row in rows:
        if not row.get("turns") or "error" in row:
            raise ValueError(
                "Every capture needs completed transport and recorded turns"
            )
        if row.get("prompt_version") != match[1]:
            raise ValueError(
                "Live captures do not match the current prompt; run and review a fresh evaluation"
            )
        if row.get("retrieval_mode") != "lexical":
            raise ValueError(
                "Evaluate the deployed lexical retrieval mode before public release"
            )
        evaluated_revision = row.get("build_revision")
        if (
            revision
            and evaluated_revision not in {None, "", "development"}
            and evaluated_revision != revision
        ):
            raise ValueError("Evaluation build revision does not match this deployment")
    if not judgments.is_file():
        raise ValueError("Human grounding judgments are required")


def release(
    config: dict,
    revision: str,
    dataset: Path,
    captures: Path,
    judgments: Path,
    provider_confirmed: bool,
) -> None:
    safeguard(config)
    if not provider_confirmed:
        raise ValueError(
            "Confirm prepaid provider funds, disabled auto-recharge, current pricing and one-call capacity before release"
        )
    check_prompt_evidence(dataset, captures, judgments, revision)
    # This evaluator also rechecks the corpus in the explicitly configured
    # evaluation database. Set its env yourself; never point tests at app.
    run(
        [
            "uv",
            "run",
            "--directory",
            "backend",
            "python",
            "scripts/evaluate_explanations.py",
            str(dataset.resolve()),
            "--captures",
            str(captures.resolve()),
            "--judgments",
            str(judgments.resolve()),
        ]
    )
    handler = run(
        gcloud(
            config,
            "run",
            "services",
            "describe",
            config["handler_service"],
            f"--region={config['region']}",
            "--format=value(status.url)",
        ),
        capture=True,
    )
    deploy_service(config, "tasks", revision, handler_url=handler, generation=True)
    api = deploy_service(config, "api", revision, handler_url=handler, generation=True)
    # Direct origin remains protected by the proxy secret in the application.
    run(
        gcloud(
            config,
            "run",
            "services",
            "add-iam-policy-binding",
            config["api_service"],
            f"--region={config['region']}",
            "--member=allUsers",
            "--role=roles/run.invoker",
        )
    )
    print(
        f"Public origin enabled at {api}; use the Cloudflare hostname for browser traffic."
    )


def schedules(config: dict) -> None:
    safeguard(config)
    origin = run(
        gcloud(
            config,
            "run",
            "services",
            "describe",
            config["handler_service"],
            f"--region={config['region']}",
            "--format=value(status.url)",
        ),
        capture=True,
    )
    for name, schedule, route in (
        ("law-padi-reconcile", "0 * * * *", "/internal/reconcile"),
        ("law-padi-backup", "0 3 * * *", "/internal/backup"),
    ):
        verb = (
            "update"
            if exists(
                gcloud(
                    config,
                    "scheduler",
                    "jobs",
                    "describe",
                    name,
                    f"--location={config['region']}",
                )
            )
            else "create"
        )
        run(
            gcloud(
                config,
                "scheduler",
                "jobs",
                verb,
                "http",
                name,
                f"--location={config['region']}",
                f"--schedule={schedule}",
                "--time-zone=Africa/Lagos",
                f"--uri={origin}{route}",
                "--http-method=POST",
                f"--oidc-service-account-email={service_account(config, 'scheduler')}",
                f"--oidc-token-audience={origin}",
                "--attempt-deadline=300s",
                "--max-retry-attempts=1",
                "--min-backoff=60s",
                "--max-backoff=300s",
            )
        )


def wrangler_command() -> list[str]:
    cached = os.environ.get("WRANGLER_CLI_JS")
    if not cached:
        return ["bunx", "wrangler@4.151.0"]
    path = Path(cached).expanduser().resolve()
    package = path.parent.parent / "package.json"
    if not path.is_file() or not package.is_file():
        raise ValueError("WRANGLER_CLI_JS must name an installed Wrangler CLI script")
    metadata = json.loads(package.read_text())
    if metadata.get("name") != "wrangler" or metadata.get("version") != "4.151.0":
        raise ValueError("The cached Wrangler CLI must match pinned version 4.151.0")
    node = shutil.which(os.environ.get("WRANGLER_NODE", "node"))
    if not node:
        raise ValueError("Install Node 22+ or set WRANGLER_NODE to its executable")
    return [node, str(path)]


def cloudflare(config: dict, revision: str, publish: bool) -> None:
    image_name(config, revision)  # Validate the build identifier before reuse.
    origin = run(
        gcloud(
            config,
            "run",
            "services",
            "describe",
            config["api_service"],
            f"--region={config['region']}",
            "--format=value(status.url)",
        ),
        capture=True,
    )
    run(
        ["bun", "run", "--filter", "frontend", "build"],
        env={**os.environ, "VITE_API_URL": "", "VITE_BUILD_REVISION": revision},
    )
    wrangler = json.loads((ROOT / "deployment/cloudflare/wrangler.json").read_text())
    wrangler["name"] = config["cloudflare_worker_name"]
    if config.get("cloudflare_account_id"):
        wrangler["account_id"] = config["cloudflare_account_id"]
    wrangler["vars"]["API_ORIGIN"] = origin
    # Paths are resolved relative to the generated config file.
    wrangler["main"] = "cloudflare/worker.ts"
    wrangler["assets"]["directory"] = "../backend/app/frontend"
    generated = ROOT / "deployment/wrangler.generated.json"
    generated.write_text(json.dumps(wrangler, indent=2) + "\n")
    if publish:
        safeguard(config)
        run([*wrangler_command(), "deploy", "--config", str(generated)])
    else:
        print(
            f"Prepared {generated}. Set VITE_API_URL='' when building; upload the matching Worker ORIGIN_PROXY_SECRET before public use."
        )


def validate_files() -> None:
    validate_config(json.loads((ROOT / "deployment/project.example.json").read_text()))
    proxy = json.loads((ROOT / "deployment/cloudflare/wrangler.json").read_text())
    assert proxy["assets"]["run_worker_first"] == ["/api/*"]
    assert proxy["assets"]["not_found_handling"] == "single-page-application"
    assert proxy["assets"]["directory"] == "../../backend/app/frontend"
    assert proxy["limits"]["cpu_ms"] <= 10
    assert "usage_model" not in proxy  # Account plan must stay Workers Free.
    print("Static deployment configuration checks passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "deployment/project.json")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "preflight", "provision", "schedules"):
        sub.add_parser(name)
    upload = sub.add_parser("upload-secrets")
    upload.add_argument("--api-env", type=Path, required=True)
    upload.add_argument("--worker-env", type=Path, required=True)
    for name in ("build", "push", "stage", "release"):
        command = sub.add_parser(name)
        command.add_argument("--revision", required=True)
        if name == "release":
            command.add_argument(
                "--dataset",
                type=Path,
                default=ROOT / "docs/constitution-explanation-evaluation-v1.json",
            )
            command.add_argument("--captures", type=Path, required=True)
            command.add_argument("--judgments", type=Path, required=True)
            command.add_argument("--provider-capacity-confirmed", action="store_true")
    cf = sub.add_parser("cloudflare")
    cf.add_argument("--revision", required=True)
    cf.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        validate_files()
        return 0
    config = json.loads(args.config.read_text())
    validate_config(config)
    if args.command == "upload-secrets":
        upload_secrets(config, args.api_env, args.worker_env, args.config)
    elif args.command == "release":
        release(
            config,
            args.revision,
            args.dataset,
            args.captures,
            args.judgments,
            args.provider_capacity_confirmed,
        )
    elif args.command == "cloudflare":
        cloudflare(config, args.revision, args.publish)
    elif args.command in {"build", "push", "stage"}:
        {"build": build, "push": push, "stage": stage}[args.command](
            config, args.revision
        )
    else:
        {"preflight": preflight, "provision": provision, "schedules": schedules}[
            args.command
        ](config)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"Deployment stopped: {exc}", file=sys.stderr)
        sys.exit(1)
