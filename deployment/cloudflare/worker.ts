interface Env {
	ASSETS: { fetch(request: Request): Promise<Response> };
	API_ORIGIN: string;
	ORIGIN_PROXY_SECRET: string;
}

type OriginFetch = (request: Request) => Promise<Response>;
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

export async function handleRequest(
	request: Request,
	env: Env,
	originFetch: OriginFetch = fetch,
): Promise<Response> {
	const url = new URL(request.url);
	if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
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
	const target = new URL(url.pathname + url.search, origin);
	const headers = new Headers(request.headers);
	headers.delete("host");
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
		// Cloudflare's cache is disabled for account/conversation/source traffic.
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
	return new Response(response.body, {
		status: response.status,
		statusText: response.statusText,
		headers: responseHeaders,
	});
}

export default {
	fetch(request: Request, env: Env): Promise<Response> {
		return handleRequest(request, env);
	},
};
