import { describe, expect, test } from "bun:test";
import worker, { handleRequest, withSecurityHeaders } from "./worker";

function env(overrides = {}) {
	return {
		ASSETS: { fetch: async () => new Response("SPA") },
		API_ORIGIN: "https://law-padi-123.us-east1.run.app",
		ORIGIN_PROXY_SECRET: "secret-in-worker",
		...overrides,
	};
}

describe("same-origin API proxy", () => {
	test("serves utility routes without invoking the API", async () => {
		const response = await handleRequest(
			new Request("https://constitution.workers.dev/saved"),
			env({ API_ORIGIN: "" }),
		);
		expect(response.status).toBe(200);
		expect(response.headers.get("x-robots-tag")).toContain("noindex");
		expect(await response.text()).toBe("SPA");
	});

	test("forwards credentials and replay headers while replacing trusted headers", async () => {
		let incoming: Request | undefined;
		const response = await handleRequest(
			new Request(
				"https://constitution.workers.dev/api/v1/conversations/abc/events?run_id=def",
				{
					headers: {
						cookie: "constitution_guest_session=session; access_token=token",
						authorization: "Bearer user-token",
						"last-event-id": "42",
						"x-origin-proxy-secret": "attacker-value",
						"cf-connecting-ip": "203.0.113.1",
						"x-forwarded-for": "attacker-ip",
						"x-forwarded-host": "attacker.example",
						forwarded: "for=attacker",
					},
				},
			),
			env(),
			async (request) => {
				incoming = request;
				return new Response("ok", {
					headers: {
						"set-cookie":
							"constitution_guest_session=new; Secure; HttpOnly; SameSite=Lax",
					},
				});
			},
		);
		expect(incoming?.url).toBe(
			"https://law-padi-123.us-east1.run.app/api/v1/conversations/abc/events?run_id=def",
		);
		expect(incoming?.headers.get("x-origin-proxy-secret")).toBe(
			"secret-in-worker",
		);
		expect(incoming?.headers.get("x-forwarded-for")).toBe("203.0.113.1");
		expect(incoming?.headers.get("x-forwarded-host")).toBe(
			"constitution.workers.dev",
		);
		expect(incoming?.headers.get("forwarded")).toBeNull();
		expect(incoming?.headers.get("last-event-id")).toBe("42");
		expect(incoming?.headers.get("cookie")).toContain("session");
		expect(incoming?.headers.get("authorization")).toBe("Bearer user-token");
		expect(incoming?.cache).toBe("no-store");
		expect(response.headers.get("set-cookie")).toContain("Secure; HttpOnly");
		expect(response.headers.get("cache-control")).toBe("private, no-store");
	});

	test("streams the first SSE chunk without waiting for the answer to finish", async () => {
		let finish: (() => void) | undefined;
		const body = new ReadableStream<Uint8Array>({
			start(controller) {
				controller.enqueue(
					new TextEncoder().encode("event: started\ndata: {}\n\n"),
				);
				finish = () => controller.close();
			},
		});
		const response = await handleRequest(
			new Request(
				"https://constitution.workers.dev/api/v1/conversations/abc/events",
			),
			env(),
			async () =>
				new Response(body, {
					headers: { "content-type": "text/event-stream" },
				}),
		);
		const first = await response.body?.getReader().read();
		expect(new TextDecoder().decode(first?.value)).toContain("event: started");
		expect(first?.done).toBe(false);
		finish?.();
	});

	test("propagates browser disconnects to the API request", async () => {
		const controller = new AbortController();
		let incoming: Request | undefined;
		await handleRequest(
			new Request(
				"https://constitution.workers.dev/api/v1/conversations/abc/events",
				{
					signal: controller.signal,
				},
			),
			env(),
			async (request) => {
				incoming = request;
				return new Response("started");
			},
		);
		expect(incoming?.signal.aborted).toBe(false);
		controller.abort();
		expect(incoming?.signal.aborted).toBe(true);
	});

	test("keeps API redirects at the public hostname and source redirects external", async () => {
		for (const [location, expected] of [
			[
				"https://law-padi-123.us-east1.run.app/api/v1/legal/",
				"https://constitution.workers.dev/api/v1/legal/",
			],
			[
				"https://r2.example.com/source.pdf?signature=example",
				"https://r2.example.com/source.pdf?signature=example",
			],
		]) {
			const response = await handleRequest(
				new Request(
					"https://constitution.workers.dev/api/v1/legal" + "/sources/a",
				),
				env(),
				async (request) => {
					expect(request.redirect).toBe("manual");
					return new Response(null, { status: 307, headers: { location } });
				},
			);
			expect(response.headers.get("location")).toBe(expected);
		}
	});

	test("proxies the Render backend and keeps its redirects on the public origin", async () => {
		const response = await handleRequest(
			new Request(
				"https://constitution.workers.dev/api/v1/legal/releases/current",
			),
			env({ API_ORIGIN: "https://constitution-ng-api.onrender.com" }),
			async (request) => {
				expect(request.url).toBe(
					"https://constitution-ng-api.onrender.com/api/v1/legal/releases/current",
				);
				expect(request.headers.get("x-origin-proxy-secret")).toBe(
					"secret-in-worker",
				);
				return new Response(null, {
					status: 307,
					headers: { location: "/api/v1/legal/releases/current/" },
				});
			},
		);
		expect(response.headers.get("location")).toBe(
			"https://constitution.workers.dev/api/v1/legal/releases/current/",
		);
	});

	test("rejects proxy destinations outside a fixed hosting origin", async () => {
		for (const origin of [
			"http://example.run.app",
			"https://attacker.example",
			"https://a.run.app/path",
			"https://user:password@a.run.app",
			"https://a.run.app?redirect=evil",
			"https://a.run.app:8443/",
			"https://a.onrender.com.evil.example",
			"https://fake-onrender.com",
			"https://a.onrender.com/path",
			"http://a.onrender.com",
		]) {
			const response = await handleRequest(
				new Request("https://constitution.workers.dev/api/v1/legal/search"),
				env({ API_ORIGIN: origin }),
			);
			expect(response.status).toBe(503);
		}
	});

	test("rejects private paths and encoded path separators", async () => {
		for (const path of [
			"/api/internal/backup",
			"/api/v2/internal",
			"/api/v1/%2finternal/backup",
			"/api/v1/%5cinternal",
			"/api/v1/%2e%2fbackup",
		]) {
			const response = await handleRequest(
				new Request(`https://constitution.workers.dev${path}`),
				env(),
				async () => {
					throw new Error("must never reach origin");
				},
			);
			expect(response.status).toBe(404);
		}
	});

	test("returns a bounded error when origin is unavailable", async () => {
		const response = await handleRequest(
			new Request("https://constitution.workers.dev/api/v1/legal/search"),
			env(),
			async () => {
				throw new Error("unavailable");
			},
		);
		expect(response.status).toBe(502);
	});
});

describe("public read cache", () => {
	const BASE = "https://constitution.example/api/v1/legal";
	const JSON_HEADERS = { "content-type": "application/json" };

	function edgeCache() {
		const stored = new Map<string, Response>();
		return {
			stored,
			match: async (key: Request) => stored.get(key.url)?.clone(),
			put: async (key: Request, response: Response) => {
				stored.set(key.url, response);
			},
		};
	}

	function background() {
		const work: Promise<unknown>[] = [];
		return {
			waitUntil: (item: Promise<unknown>) => work.push(item),
			settled: () => Promise.all(work),
		};
	}

	async function read(
		path: string,
		cache: ReturnType<typeof edgeCache>,
		origin: (request: Request) => Response,
		init: RequestInit = {},
	) {
		const queue = background();
		const response = await handleRequest(
			new Request(`${BASE}/${path}`, init),
			env(),
			async (request) => origin(request),
			queue,
			cache,
		);
		const body = await response.text();
		await queue.settled();
		return { response, body };
	}

	test("serves a repeated read from the cache without calling the API", async () => {
		const cache = edgeCache();
		let calls = 0;
		const origin = () => {
			calls += 1;
			return new Response('{"ok":true}', { headers: JSON_HEADERS });
		};
		const first = await read("instruments", cache, origin);
		const second = await read("instruments", cache, origin);
		expect(calls).toBe(1);
		expect(first.response.headers.get("x-edge-cache")).toBe("miss");
		expect(second.response.headers.get("x-edge-cache")).toBe("hit");
		expect(second.body).toBe('{"ok":true}');
		expect(second.response.headers.get("cache-control")).toBe(
			"public, max-age=60",
		);
		expect(second.response.headers.get("x-robots-tag")).toBe("noindex");
	});

	test("keeps pinned reads longer than current reads", async () => {
		const cache = edgeCache();
		const origin = () => new Response("{}");
		await read("provisions/tree", cache, origin);
		await read("provisions/tree?release_version=v1", cache, origin);
		const ages = [...cache.stored.values()].map((item) =>
			item.headers.get("cache-control"),
		);
		expect(ages).toEqual(["public, max-age=300", "public, max-age=3600"]);
	});

	test("shares a read between visitors without sending their credentials", async () => {
		const cache = edgeCache();
		let incoming: Request | undefined;
		const origin = (request: Request) => {
			incoming = request;
			return new Response("{}", {
				headers: { vary: "Origin", "access-control-allow-origin": "x" },
			});
		};
		await read("instruments", cache, origin, {
			headers: { cookie: "access_token=a", authorization: "Bearer a" },
		});
		expect(incoming?.headers.get("cookie")).toBeNull();
		expect(incoming?.headers.get("authorization")).toBeNull();
		expect(incoming?.headers.get("x-origin-proxy-secret")).toBe(
			"secret-in-worker",
		);
		const [stored] = cache.stored.values();
		expect(stored?.headers.get("vary")).toBeNull();
		expect(stored?.headers.get("access-control-allow-origin")).toBeNull();
	});

	test("treats reordered parameters as one read", async () => {
		const cache = edgeCache();
		const origin = () => new Response("{}");
		await read(
			"provisions/tree?instrument=a&release_version=v1",
			cache,
			origin,
		);
		await read(
			"provisions/tree?release_version=v1&instrument=a",
			cache,
			origin,
		);
		expect(cache.stored.size).toBe(1);
	});

	test.each([
		["unknown parameter", "instruments?cache_buster=1", 200],
		["failed read", "instruments", 503],
		["missing provision", "provisions/absent", 404],
		["source redirect", "sources/abc/content", 307],
		["route outside the list", "provisions-export", 200],
	])("does not store a %s", async (_label, path, status) => {
		const cache = edgeCache();
		const { response } = await read(
			path,
			cache,
			() => new Response(null, { status }),
		);
		expect(cache.stored.size).toBe(0);
		expect(response.headers.get("cache-control")).toBe("private, no-store");
		expect(response.headers.get("x-edge-cache")).toBeNull();
	});

	test("does not store a response that sets a cookie", async () => {
		const cache = edgeCache();
		const { response } = await read(
			"instruments",
			cache,
			() => new Response("{}", { headers: { "set-cookie": "a=b" } }),
		);
		expect(cache.stored.size).toBe(0);
		expect(response.headers.get("cache-control")).toBe("private, no-store");
	});

	test("leaves other methods and private routes alone", async () => {
		const cache = edgeCache();
		const origin = () => new Response("{}");
		await read("search", cache, origin, { method: "POST", body: "{}" });
		await read("instruments", cache, origin, { method: "HEAD" });
		const queue = background();
		await handleRequest(
			new Request("https://constitution.example/api/v1/conversations/abc", {
				headers: { cookie: "constitution_guest_session=a" },
			}),
			env(),
			async () => new Response("{}"),
			queue,
			cache,
		);
		await queue.settled();
		expect(cache.stored.size).toBe(0);
	});

	test("falls back to the API when the cache is unavailable", async () => {
		const queue = background();
		const response = await handleRequest(
			new Request(`${BASE}/instruments`),
			env(),
			async () => new Response('{"ok":true}'),
			queue,
			{
				match: async () => {
					throw new Error("cache unavailable");
				},
				put: async () => {
					throw new Error("cache unavailable");
				},
			},
		);
		expect(await response.text()).toBe('{"ok":true}');
		await queue.settled();
	});

	test("works where no cache exists, such as workers.dev", async () => {
		const response = await handleRequest(
			new Request(`${BASE}/instruments`),
			env(),
			async () => new Response("{}"),
			undefined,
			undefined,
		);
		expect(response.status).toBe(200);
		expect(response.headers.get("cache-control")).toBe("public, max-age=60");
	});
});

describe("security headers", () => {
	test("every response refuses framing and plugins", async () => {
		const response = await worker.fetch(
			new Request("https://constitution.workers.dev/saved"),
			env({ API_ORIGIN: "" }),
			{ waitUntil: () => undefined },
		);
		expect(await response.text()).toBe("SPA");
		expect(response.headers.get("content-security-policy")).toContain(
			"frame-ancestors 'none'",
		);
		expect(response.headers.get("x-frame-options")).toBe("DENY");
		expect(response.headers.get("x-content-type-options")).toBe("nosniff");
	});

	test("keeps a header the page already set and works on immutable responses", () => {
		const immutable = Response.redirect("https://constitution.workers.dev/", 302);
		const secured = withSecurityHeaders(immutable);
		expect(secured.status).toBe(302);
		expect(secured.headers.get("referrer-policy")).toBe(
			"strict-origin-when-cross-origin",
		);
		const own = withSecurityHeaders(
			new Response("ok", { headers: { "referrer-policy": "no-referrer" } }),
		);
		expect(own.headers.get("referrer-policy")).toBe("no-referrer");
	});
});
