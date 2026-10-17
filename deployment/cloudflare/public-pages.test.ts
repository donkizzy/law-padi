import { describe, expect, test } from "bun:test";
import { handleRequest } from "./worker";

const origin = "https://constitition-ng.amosgodwin500.workers.dev";
const sectionPath = "constitution-1999.chapter4.section37";
const chapter = {
	id: "chapter",
	canonical_path: "constitution-1999.chapter4",
	kind: "chapter",
	citation: "Chapter 4",
	title: "Fundamental rights",
	has_text: false,
};
const section = {
	id: "section",
	canonical_path: sectionPath,
	kind: "section",
	citation: "Section 37",
	title: "Right to private and family life",
	has_text: true,
};
const provision = {
	...section,
	authoritative_text: "The privacy of citizens is protected.",
	release_version: "published-2004",
	edition_label: "Historical/source Constitution compilation (LFN 2004)",
	legal_status: "historical",
	source_authority: "Official Gazette",
	source_title: "Source PDF",
	source_url: "https://example.org/source.pdf",
	source_page_start: 38,
	ancestors: [chapter],
	children: [],
};
const shell =
	'<!DOCTYPE html><html lang="en"><head><title>old title</title><meta name="description" content="old description"></head><body><div id="root"></div><script src="/assets/index-Abcdef12.js"></script></body></html>';
const env = {
	ASSETS: {
		fetch: async (request: Request) =>
			new URL(request.url).pathname === "/"
				? new Response(shell, { headers: { "content-type": "text/html" } })
				: new URL(request.url).pathname.startsWith("/assets/")
					? new Response("asset", {
							headers: { "content-type": "text/javascript" },
						})
					: new Response("Missing", { status: 404 }),
	},
	API_ORIGIN: "https://constitution-ng-api.onrender.com",
	ORIGIN_PROXY_SECRET: "test-secret",
	PUBLIC_SITE_URL: origin,
};
function backend(request: Request): Promise<Response> {
	const url = new URL(request.url);
	expect(request.headers.get("cookie")).toBeNull();
	expect(request.headers.get("authorization")).toBeNull();
	expect(request.headers.get("x-origin-proxy-secret")).toBe("test-secret");
	if (url.pathname.endsWith("/tree"))
		return Promise.resolve(
			Response.json({
				data: url.searchParams.has("all_nodes")
					? [chapter, section]
					: [section],
				scope: url.searchParams.has("all_nodes") ? "all" : "children",
				parent: url.searchParams.has("parent_path") ? chapter : null,
				release_version: provision.release_version,
				edition_label: provision.edition_label,
			}),
		);
	if (url.pathname.endsWith(sectionPath))
		return Promise.resolve(Response.json({ data: [provision] }));
	return Promise.resolve(new Response("Not found", { status: 404 }));
}
function get(path: string, fetcher = backend, method = "GET") {
	return handleRequest(
		new Request(origin + path, {
			method,
			headers: {
				cookie: "private-session",
				authorization: "Bearer private-token",
			},
		}),
		env,
		fetcher,
	);
}

describe("public reading and discovery responses", () => {
	test("serves the retained benchmark without requiring repository access", async () => {
		const response = await get("/methodology/benchmark.json");
		expect(response.status).toBe(200);
		expect(response.headers.get("content-type")).toContain("application/json");
		const data = await response.json();
		expect(data.version).toBe("plain-language-retrieval-v1");
		expect(data.cases.length).toBe(55);
	});

	test("serves landing text, identity and exactly one metadata set before JavaScript", async () => {
		const response = await get("/welcome");
		const html = await response.text();
		expect(response.status).toBe(200);
		expect(html).toContain("Ask about your rights");
		expect(html).toContain("Later amendments");
		expect(html.match(/<title\b/g)?.length).toBe(1);
		expect(html.match(/name="description"/g)?.length).toBe(1);
		expect(html).toContain(`rel="canonical" href="${origin}/welcome"`);
		expect(html).toContain('"@type":"Organization"');
		expect(html).not.toContain("Amos");
	});
	test("pins current aliases and renders historical text, source and breadcrumbs", async () => {
		const alias = await get(`/constitution/${sectionPath}`);
		expect(alias.status).toBe(302);
		expect(alias.headers.get("location")).toBe(
			`${origin}/constitution/${sectionPath}?release=published-2004`,
		);
		const response = await get(
			`/constitution/${sectionPath}?release=published-2004`,
		);
		const html = await response.text();
		expect(html).toContain(provision.authoritative_text);
		expect(html).toContain("printed page 38");
		expect(html).toContain("Later amendments");
		expect(html).toContain('"@type":"BreadcrumbList"');
		expect(html).toContain('id="public-corpus-data"');
		expect(response.headers.get("cache-control")).toBe("private, no-store");
	});
	test("renders chapter links without clicks and pins hub identity", async () => {
		const response = await get(
			`/constitution?parent=${chapter.canonical_path}&release=published-2004`,
		);
		expect(await response.text()).toContain(
			`href="/constitution/${sectionPath}?release=published-2004"`,
		);
		expect(response.status).toBe(200);
	});
	test("returns real missing/error statuses, keeping outages distinct from missing law", async () => {
		expect((await get("/not-a-real-page")).status).toBe(404);
		expect(
			(await get("/constitution/missing?release=published-2004")).status,
		).toBe(404);
		const unavailable = await get(
			`/constitution/${sectionPath}?release=published-2004`,
			async () => new Response("down", { status: 503 }),
		);
		expect(unavailable.status).toBe(503);
		expect(unavailable.headers.get("retry-after")).toBe("60");
		expect(unavailable.headers.get("x-robots-tag")).toContain("noindex");
		expect((await get("/ai-catalog.json")).status).toBe(404);
		expect((await get("/constitution/a%2Fb")).status).toBe(404);
	});
	test("unpublishes the fixture amendment route in HTML and on the wire", async () => {
		const response = await get("/amendments");
		const html = await response.text();
		expect(response.status).toBe(410);
		expect(response.headers.get("x-robots-tag")).toContain("noindex");
		expect(html).not.toContain("First Alteration");
		expect(html).toContain("not published here yet");
	});
	test("serves actual crawler and optional LLM directory files", async () => {
		const response = await get("/robots.txt");
		expect(response.headers.get("content-type")).toContain("text/plain");
		const robots = await response.text();
		for (const agent of ["OAI-SearchBot", "Claude-SearchBot", "PerplexityBot"])
			expect(robots).toContain(agent);
		expect(robots).toContain(`Sitemap: ${origin}/sitemap.xml`);
		expect(robots).not.toContain("Disallow: /\n");
		expect(await (await get("/llms.txt")).text()).toContain(
			"release-pinned canonical URL",
		);
	});
	test("builds the sitemap only from a complete published index, without fake dates", async () => {
		const response = await get("/sitemap.xml");
		const xml = await response.text();
		expect(response.headers.get("content-type")).toContain("application/xml");
		expect(xml).toContain(`${sectionPath}?release=published-2004`);
		expect(xml).toContain(
			"parent=constitution-1999.chapter4&amp;release=published-2004",
		);
		expect(xml).not.toContain("lastmod");
		expect(xml).not.toContain("amendments");
		expect(
			(
				await get("/sitemap.xml", async () =>
					Response.json({
						data: [chapter],
						release_version: "old-api",
						edition_label: "source",
					}),
				)
			).status,
		).toBe(503);
	});
	test("keeps utility/search/noisy states out of the index and implements HEAD", async () => {
		for (const path of [
			"/login",
			"/saved",
			"/settings",
			"/?q=private",
			"/welcome?unknown=value",
		])
			expect((await get(path)).headers.get("x-robots-tag")).toContain(
				"noindex",
			);
		const head = await get("/welcome", backend, "HEAD");
		expect(head.status).toBe(200);
		expect(await head.text()).toBe("");
		expect((await get("/welcome", backend, "POST")).status).toBe(405);
		const alternate = await handleRequest(
			new Request("https://preview.example/welcome"),
			env,
			backend,
		);
		expect(alternate.headers.get("x-robots-tag")).toContain("noindex");
	});
	test("escapes corpus text and JSON and refuses script source URLs", async () => {
		const response = await get(
			`/constitution/${sectionPath}?release=published-2004`,
			async () =>
				Response.json({
					data: [
						{
							...provision,
							title: "</title><script>alert(1)</script>",
							authoritative_text: '<img src=x onerror="alert(1)">',
							source_url: "javascript:alert(1)",
						},
					],
				}),
		);
		const html = await response.text();
		expect(html).not.toContain("<script>alert(1)</script>");
		expect(html).toContain("&lt;img");
		expect(html).not.toContain('href="javascript:');
		expect(html).toContain("\\u003c/script>");
	});
	test("caches fingerprinted assets immutably without changing HTML/API caching", async () => {
		const response = await get("/assets/index-Abcdef12.js");
		expect(response.headers.get("cache-control")).toContain("immutable");
		expect((await get("/welcome")).headers.get("cache-control")).toBe(
			"private, no-store",
		);
	});
});
