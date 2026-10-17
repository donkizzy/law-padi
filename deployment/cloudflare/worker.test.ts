import { describe, expect, test } from "bun:test";
import { handleRequest } from "./worker";

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
