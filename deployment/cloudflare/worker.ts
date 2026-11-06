import { publicRequest } from "./public-pages";

interface Env {
	ASSETS: { fetch(request: Request): Promise<Response> };
	API_ORIGIN: string;
	ORIGIN_PROXY_SECRET: string;
	PUBLIC_SITE_URL?: string;
}

type OriginFetch = (request: Request) => Promise<Response>;
interface EdgeCache {
	match(key: Request): Promise<Response | undefined>;
	put(key: Request, response: Response): Promise<void>;
}
interface BackgroundWork {
	waitUntil(work: Promise<unknown>): void;
}
interface PublicRead {
	key: Request;
	ttlSeconds: number;
}

// Raise after an urgent correction: the Cache API cannot purge every location.
const EDGE_CACHE_VERSION = "1";
// Published wording is fixed per release, but source titles and display data
// can still be corrected, so even pinned reads expire.
const PINNED_READ_TTL_SECONDS = 60 * 60;
const CURRENT_READ_TTL_SECONDS = 5 * 60;
const BROWSER_TTL_SECONDS = 60;
const PUBLIC_READ =
	/^\/api\/v1\/legal\/(?:instruments|releases\/current|provision-history|provisions\/.+)$/;
const PUBLIC_READ_PARAMS = new Set([
	"all_nodes",
	"canonical_path",
	"citation",
	"index_kind",
	"instrument",
	"parent_path",
	"release_version",
]);
// None of these can change a public read, and each would split or vary the cache.
const PRIVATE_READ_HEADERS = [
	"authorization",
	"cookie",
	"if-modified-since",
	"if-none-match",
	"origin",
	"range",
];
const PROXY_HEADER = "x-origin-proxy-secret";
const FORWARDED_HEADERS = [
	"forwarded",
	"x-forwarded-for",
	"x-forwarded-host",
	"x-forwarded-proto",
	"x-real-ip",
];
const METHODS = new Set([
	"GET",
	"HEAD",
	"POST",
	"PUT",
	"PATCH",
	"DELETE",
	"OPTIONS",
]);

function backendOrigin(value: string): URL | null {
	try {
		const origin = new URL(value);
		if (
			origin.protocol !== "https:" ||
			!(
				origin.hostname.endsWith(".run.app") ||
				origin.hostname.endsWith(".onrender.com")
			) ||
			origin.username ||
			origin.password ||
			origin.port ||
			origin.pathname !== "/" ||
			origin.search ||
			origin.hash
		)
			return null;
		return origin;
	} catch {
		return null;
	}
}

function publicRead(url: URL, method: string): PublicRead | null {
	if (method !== "GET" || !PUBLIC_READ.test(url.pathname)) return null;
	const params = [...url.searchParams.entries()];
	if (params.some(([name]) => !PUBLIC_READ_PARAMS.has(name))) return null;
	const query = new URLSearchParams([
		["edge_cache_version", EDGE_CACHE_VERSION],
		...params.sort(([a], [b]) => a.localeCompare(b)),
	]);
	return {
		key: new Request(`${url.origin}${url.pathname}?${query}`),
		ttlSeconds: url.searchParams.has("release_version")
			? PINNED_READ_TTL_SECONDS
			: CURRENT_READ_TTL_SECONDS,
	};
}

function defaultEdgeCache(): EdgeCache | undefined {
	return (globalThis as { caches?: { default?: EdgeCache } }).caches?.default;
}

async function cachedRead(
	edgeCache: EdgeCache | undefined,
	read: PublicRead | null,
): Promise<Response | null> {
	if (!edgeCache || !read) return null;
	try {
		const cached = await edgeCache.match(read.key);
		if (!cached) return null;
		const headers = new Headers(cached.headers);
		headers.delete("age");
		headers.set("cache-control", `public, max-age=${BROWSER_TTL_SECONDS}`);
		headers.set("x-edge-cache", "hit");
		return new Response(cached.body, { status: cached.status, headers });
	} catch {
		return null;
	}
}

function storedRead(response: Response, ttlSeconds: number): Response {
	const headers = new Headers(response.headers);
	headers.set("cache-control", `public, max-age=${ttlSeconds}`);
	for (const name of ["vary", "x-edge-cache"]) headers.delete(name);
	for (const name of [...headers.keys()]) {
		if (name.startsWith("access-control-")) headers.delete(name);
	}
	return new Response(response.body, { status: response.status, headers });
}

export async function handleRequest(
	request: Request,
	env: Env,
	originFetch: OriginFetch = fetch,
	background?: BackgroundWork,
	edgeCache: EdgeCache | undefined = defaultEdgeCache(),
): Promise<Response> {
	const url = new URL(request.url);
	if (!url.pathname.startsWith("/api/")) {
		return publicRequest(request, env, (path) =>
			handleRequest(
				new Request(new URL(path, url.origin), {
					headers: { accept: "application/json" },
					signal: AbortSignal.any([
						request.signal,
						AbortSignal.timeout(15_000),
					]),
				}),
				env,
				originFetch,
				background,
				edgeCache,
			),
		);
	}
	// Only the public API namespace may reach the backend. In particular, the
	// private task endpoints never have a route through the public Worker.
	if (
		!url.pathname.startsWith("/api/v1/") ||
		/%(?:2f|5c|2e)|\\/i.test(url.pathname) ||
		!METHODS.has(request.method)
	)
		return new Response("Not found", { status: 404 });
	const origin = backendOrigin(env.API_ORIGIN);
	if (!origin || !env.ORIGIN_PROXY_SECRET) {
		return new Response("Service configuration unavailable", { status: 503 });
	}
	const read = publicRead(url, request.method);
	const cached = await cachedRead(edgeCache, read);
	if (cached) return cached;
	const target = new URL(url.pathname + url.search, origin);
	const headers = new Headers(request.headers);
	headers.delete("host");
	if (read) for (const name of PRIVATE_READ_HEADERS) headers.delete(name);
	for (const name of FORWARDED_HEADERS) headers.delete(name);
	// The browser cannot choose the proxy credential or trusted client IP.
	headers.set(PROXY_HEADER, env.ORIGIN_PROXY_SECRET);
	const clientIP = request.headers.get("cf-connecting-ip");
	if (clientIP) headers.set("x-forwarded-for", clientIP);
	headers.set("x-forwarded-host", url.host);
	headers.set("x-forwarded-proto", "https");
	const upstream = new Request(target, {
		method: request.method,
		headers,
		body: request.body,
		signal: request.signal,
		redirect: "manual",
		cache: "no-store",
		// Only allow-listed public reads are stored, explicitly and by key, so
		// account/conversation/source traffic never enters Cloudflare's cache.
		// Static assets continue using the separate ASSETS binding.
	});
	let response: Response;
	try {
		response = await originFetch(upstream);
	} catch {
		return new Response("API temporarily unavailable", { status: 502 });
	}
	const responseHeaders = new Headers(response.headers);
	responseHeaders.set("cache-control", "private, no-store");
	responseHeaders.set("x-robots-tag", "noindex");
	responseHeaders.delete(PROXY_HEADER);
	const location = responseHeaders.get("location");
	if (location) {
		const redirect = new URL(location, target);
		if (redirect.origin === origin.origin) {
			responseHeaders.set(
				"location",
				url.origin + redirect.pathname + redirect.search + redirect.hash,
			);
		}
	}
	// Keep the original stream. Reading text()/json()/arrayBuffer() here would
	// buffer SSE, delaying answers and losing disconnect propagation.
	const shareable =
		read && response.status === 200 && !response.headers.has("set-cookie");
	if (shareable) {
		responseHeaders.set(
			"cache-control",
			`public, max-age=${BROWSER_TTL_SECONDS}`,
		);
		responseHeaders.set("x-edge-cache", "miss");
	}
	const proxied = new Response(response.body, {
		status: response.status,
		statusText: response.statusText,
		headers: responseHeaders,
	});
	if (shareable && edgeCache && background) {
		background.waitUntil(
			edgeCache
				.put(read.key, storedRead(proxied.clone(), read.ttlSeconds))
				.catch(() => undefined),
		);
	}
	return proxied;
}

export default {
	fetch(
		request: Request,
		env: Env,
		background: BackgroundWork,
	): Promise<Response> {
		return handleRequest(request, env, fetch, background);
	},
};
