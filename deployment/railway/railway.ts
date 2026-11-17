/**
 * Railway project for the constitution.ng API, workers and database.
 *
 * Railway Infrastructure as Code: preview with
 *   railway config plan --file deployment/railway/railway.ts
 * and apply with `railway config apply --file deployment/railway/railway.ts`.
 * Railway does not read this file during deploys; it holds the service
 * settings and variables that `apply` writes. The procedure, the variables
 * set by hand and the reasons for each setting are in
 * deployment/railway/README.md and docs/runbooks/railway-migration.md.
 *
 * Nothing that names the deployment is tracked: the GitHub repository comes
 * from RAILWAY_GITHUB_REPO when the plan runs, generated domains are created
 * in the dashboard, and every credential is a Railway variable set by hand.
 */
import {
	defineRailway,
	github,
	preserve,
	service,
	type VariableValue,
	volume,
} from "railway/iac";

const repository = process.env.RAILWAY_GITHUB_REPO;
if (!repository) {
	throw new Error("Set RAILWAY_GITHUB_REPO to the owner/name of the repository");
}

const BRANCH = "master";
// EU West (Amsterdam) is Railway's region closest to Nigerian readers. The
// database volume, the database and the services that query it share one
// region, so every query stays on the private network.
const REGION = "europe-west4-drams3a";

// Railway's deploy health check sends this Host header and cannot send the
// origin credential (backend/app/main.py, PLATFORM_HEALTHCHECK_HOST).
const HEALTHCHECK_HOST = "healthcheck.railway.app";

// Watch patterns. A push rebuilds a service only when a file it is built
// from changes. The api is built from everything scripts/build_revision.py
// hashes, so the revision it reports always matches the frontend built from
// the same commit; the chat worker shares its image but needs only the
// backend, so a frontend-only change leaves it running.
const backendRuntime = [
	"backend/app/**",
	"backend/alembic.ini",
	"backend/pyproject.toml",
	"backend/Dockerfile",
	"pyproject.toml",
	"uv.lock",
	".dockerignore",
	"deployment/railway/run.sh",
];
const apiInputs = [
	...backendRuntime,
	"backend/scripts/prestart.sh",
	"package.json",
	"bun.lock",
	"frontend/package.json",
	"frontend/index.html",
	"frontend/vite.config.ts",
	"frontend/tsconfig*.json",
	"frontend/playwright.config.ts",
	"frontend/tests/backend-specs.ts",
	"frontend/src/**",
	"frontend/public/**",
	"eval/datasets/plain-language-retrieval-benchmark-v1.json",
	"deployment/cloudflare/worker.ts",
	"deployment/cloudflare/public-pages.ts",
	"deployment/cloudflare/pages.ts",
	"deployment/cloudflare/html.ts",
	"deployment/cloudflare/wrangler.json",
	"deployment/cloudflare/tsconfig.json",
	"deployment/render/Dockerfile",
	"deployment/render/start.sh",
	"scripts/build_revision.py",
];
const ingestionInputs = [
	"backend/app/**",
	"services/ingestion-worker/**",
	".dockerignore",
	"deployment/railway/run.sh",
];

// Project shared variables, set once by hand in the dashboard (Project
// Settings, Shared Variables) and referenced by every service that needs them.
function shared(name: string): string {
	return `\${{shared.${name}}}`;
}

const pgdata = volume("pgdata", { region: REGION });

const postgres = service("postgres", {
	source: github(repository, {
		branch: BRANCH,
		rootDirectory: "deployment/railway/postgres",
		checkSuites: true,
	}),
	build: {
		builder: "DOCKERFILE",
		dockerfilePath: "Dockerfile",
		watchPatterns: ["deployment/railway/postgres/**"],
	},
	regions: { [REGION]: 1 },
	deploy: {
		restartPolicyType: "ALWAYS",
		sleepApplication: false,
		// Postgres finishes a fast shutdown, with a checkpoint, in this time.
		drainingSeconds: 60,
	},
	// The volume root holds PGDATA (/var/lib/postgresql/18/docker, the image
	// default) and the TLS certificate (tls/), so the volume's lost+found
	// never sits inside the data directory.
	volumeMounts: { "/var/lib/postgresql": pgdata },
	// Operators, corpus releases and the backup workflow connect through the
	// TCP proxy over TLS; the services use the private network.
	tcp: [5432],
	env: {
		POSTGRES_USER: "postgres",
		POSTGRES_DB: "app",
		// Set by hand: 64 hex characters (openssl rand -hex 32), so the URLs
		// below need no escaping.
		POSTGRES_PASSWORD: preserve(),
		PGDATA: "/var/lib/postgresql/18/docker",
		DATABASE_URL:
			"postgresql://${{POSTGRES_USER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:5432/${{POSTGRES_DB}}",
		DATABASE_PUBLIC_URL:
			"postgresql://${{POSTGRES_USER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_TCP_PROXY_DOMAIN}}:${{RAILWAY_TCP_PROXY_PORT}}/${{POSTGRES_DB}}?sslmode=verify-full",
	},
});

// Settings every application process validates at start (app/core/config.py).
const core: Record<string, string | VariableValue> = {
	PROJECT_NAME: "constitution.ng",
	SECRET_KEY: shared("SECRET_KEY"),
	FIRST_SUPERUSER: shared("FIRST_SUPERUSER"),
	FIRST_SUPERUSER_PASSWORD: shared("FIRST_SUPERUSER_PASSWORD"),
	DATABASE_URL: postgres.env.DATABASE_URL,
	DATABASE_CONNECT_TIMEOUT_SECONDS: "15",
	DATABASE_STATEMENT_TIMEOUT_MS: "30000",
	DATABASE_LOCK_TIMEOUT_MS: "5000",
	LOG_FORMAT: "json",
	// Optional, so not a shared reference: a reference to a shared variable
	// that was never created would reach the settings as unusable text. Set it
	// by hand on a service to turn error reporting on there.
	SENTRY_DSN: preserve(),
	SENTRY_ENVIRONMENT: "production",
};

// Retrieval and generation settings read by both the api (admission, search
// and query understanding) and the chat worker (answers). Values are those
// that ran on Render (render.yaml), so the move changes no reader-facing limit.
const generation: Record<string, string | VariableValue> = {
	CHAT_ENABLED: "true",
	CHAT_GENERATION_ENABLED: "true",
	CHAT_GENERATION_KILL_SWITCH: "false",
	CHAT_LANGUAGES_ENABLED: '["en","pcm","yo","ha","ig"]',
	DEEPSEEK_MODEL: "deepseek-flash",
	DEEPSEEK_API_KEY: shared("DEEPSEEK_API_KEY"),
	CHAT_PROVIDER_CAPACITY_APPROVED: "false",
	CHAT_DISPATCH_MODE: "poll",
	// One answer is generated at a time; up to five questions wait in order.
	CHAT_MAX_ACTIVE_GENERATIONS: "5",
	CHAT_WORKER_CONCURRENCY: "1",
	CHAT_DAILY_BUDGET_USD: "5",
	CHAT_MONTHLY_BUDGET_USD: "155",
	AI_MONTHLY_BUDGET_USD: "155",
	CHAT_GUEST_DAILY_LIMIT: "3",
	CHAT_ACCOUNT_DAILY_LIMIT: "10",
	CHAT_GUEST_BURST_LIMIT: "1",
	CHAT_ACCOUNT_BURST_LIMIT: "2",
	EMBEDDING_QUERY_ENABLED: "true",
	HUGGINGFACE_TEI_ENDPOINT_URL:
		"https://router.huggingface.co/hf-inference/models/BAAI/bge-m3/pipeline/feature-extraction",
	HUGGINGFACE_API_TOKEN: shared("HUGGINGFACE_API_TOKEN"),
};

const r2: Record<string, string | VariableValue> = {
	INGESTION_STORAGE_BACKEND: "r2",
	R2_ENDPOINT_URL: shared("R2_ENDPOINT_URL"),
	R2_BUCKET_NAME: shared("R2_BUCKET_NAME"),
	R2_ACCESS_KEY_ID: shared("R2_ACCESS_KEY_ID"),
	R2_SECRET_ACCESS_KEY: shared("R2_SECRET_ACCESS_KEY"),
};

const api = service("api", {
	source: github(repository, { branch: BRANCH, checkSuites: true }),
	build: {
		builder: "DOCKERFILE",
		dockerfilePath: "backend/Dockerfile",
		watchPatterns: apiInputs,
	},
	regions: { [REGION]: 1 },
	deploy: {
		startCommand: "sh /app/deployment/railway/run.sh api",
		// Once per deploy, in its own container on the private network, before
		// the new version starts. A failure stops the deploy; the running
		// version keeps serving.
		preDeployCommand: ["alembic upgrade head"],
		preDeployTimeoutSeconds: 600,
		// Railway calls the health check only while a deploy starts, to decide
		// when to move traffic, and never restarts on it. That is a readiness
		// decision, so it uses /readyz: database reachable and schema at this
		// build's head.
		healthcheckPath: "/readyz",
		healthcheckTimeout: 120,
		restartPolicyType: "ON_FAILURE",
		restartPolicyMaxRetries: 10,
		sleepApplication: false,
		// Time to close SSE streams; readers reconnect with Last-Event-ID.
		drainingSeconds: 15,
		overlapSeconds: 10,
	},
	env: {
		...core,
		...generation,
		...r2,
		APP_RUNTIME_ROLE: "api",
		SERVE_FRONTEND: "false",
		ORIGIN_PROXY_SECRET: shared("ORIGIN_PROXY_SECRET"),
		PLATFORM_HEALTHCHECK_HOST: HEALTHCHECK_HOST,
		// The Worker's public origin (PUBLIC_SITE_URL in Cloudflare).
		FRONTEND_HOST: shared("FRONTEND_HOST"),
		// Request concurrency is gated at the pool size; see the connection
		// budget in deployment/railway/README.md.
		DATABASE_POOL_SIZE: "5",
	},
});

const chatWorker = service("chat-worker", {
	source: github(repository, { branch: BRANCH, checkSuites: true }),
	build: {
		builder: "DOCKERFILE",
		dockerfilePath: "backend/Dockerfile",
		watchPatterns: backendRuntime,
	},
	regions: { [REGION]: 1 },
	deploy: {
		startCommand:
			"sh /app/deployment/railway/run.sh worker /tmp/chat-worker.heartbeat 2 30 -- python -m app.chat.worker",
		// The worker must never stop for good: a clean exit is restarted too.
		restartPolicyType: "ALWAYS",
		sleepApplication: false,
		// SIGTERM cancels the asyncio runner: a run that has not dispatched a
		// paid call returns to the queue, one that may have is settled.
		drainingSeconds: 30,
	},
	env: {
		...core,
		...generation,
		CHAT_WORKER_HEARTBEAT_FILE: "/tmp/chat-worker.heartbeat",
		WORKER_STOP_TIMEOUT: "25",
		DATABASE_POOL_SIZE: "4",
	},
});

const ingestionWorker = service("ingestion-worker", {
	source: github(repository, { branch: BRANCH, checkSuites: true }),
	build: {
		builder: "DOCKERFILE",
		dockerfilePath: "services/ingestion-worker/Dockerfile",
		watchPatterns: ingestionInputs,
	},
	regions: { [REGION]: 1 },
	deploy: {
		startCommand:
			"sh /app/deployment/railway/run.sh worker /tmp/ingestion-worker.heartbeat 5 180 -- python -m ingestion_worker.cli",
		// ON_FAILURE, so WORKER_ENABLED=false (a clean exit) keeps it stopped.
		restartPolicyType: "ON_FAILURE",
		restartPolicyMaxRetries: 10,
		// Polling the database is outbound traffic, so Railway's app sleeping
		// would never put this worker to sleep. It runs on demand instead.
		sleepApplication: false,
		// The worker stops between pages and embedding batches.
		drainingSeconds: 60,
	},
	env: {
		...core,
		...r2,
		HUGGINGFACE_TEI_ENDPOINT_URL: generation.HUGGINGFACE_TEI_ENDPOINT_URL,
		HUGGINGFACE_API_TOKEN: shared("HUGGINGFACE_API_TOKEN"),
		// Off between corpus runs. For a run, set it to true in the dashboard
		// and back to false afterwards; `railway config apply` also resets it
		// (deployment/railway/README.md).
		WORKER_ENABLED: "false",
		WORKER_STOP_TIMEOUT: "55",
		INGESTION_WORKER_ID: "railway-ingestion-worker",
		INGESTION_WORKER_POLL_INTERVAL_SECONDS: "5",
		INGESTION_WORKER_LEASE_SECONDS: "900",
		INGESTION_WORKER_HEARTBEAT_FILE: "/tmp/ingestion-worker.heartbeat",
		DATABASE_POOL_SIZE: "5",
	},
});

export default defineRailway((_ctx, project) =>
	project("constitution-ng", {
		resources: [pgdata, postgres, api, chatWorker, ingestionWorker],
	}),
);
