import { describe, expect, test } from "bun:test";
import { backend, env, get, origin, provision, sectionPath } from "./fixtures";
import { handleRequest } from "./worker";

// These pin the crawler-visible output of every edge-rendered route, so the
// templates and the content they share with the React pages can be refactored
// without silently changing titles, descriptions, canonical URLs, JSON-LD,
// markup or sitemap entries.

const release = provision.release_version;
const routes = [
	"/welcome",
	"/about",
	"/methodology",
	"/amendments",
	"/login",
	"/",
	"/not-a-real-page",
	"/laws",
	`/laws/constitution-1999?release=${release}`,
	`/laws/constitution-1999?release=${release}&parent=constitution-1999.chapter4`,
	`/laws/constitution-1999/${sectionPath}?release=${release}`,
];

function head(html: string) {
	const meta = [...html.matchAll(/<meta data-public-head [^>]*>/g)].map(
		(match) => match[0],
	);
	return {
		title: html.match(/<title data-public-head>(.*?)<\/title>/)?.[1],
		meta,
		canonical: html.match(/<link data-public-head rel="canonical" href="([^"]*)">/)?.[1],
		schema: [
			...html.matchAll(
				/<script data-public-head type="application\/ld\+json">(.*?)<\/script>/g,
			),
		].map((match) => JSON.parse(match[1])),
	};
}

describe("edge output is pinned", () => {
	for (const path of routes)
		test(`renders ${path} unchanged`, async () => {
			const response = await get(path);
			const html = response.status === 302 ? "" : await response.text();
			expect({
				status: response.status,
				location: response.headers.get("location"),
				robots: response.headers.get("x-robots-tag"),
				link: response.headers.get("link"),
				html,
			}).toMatchSnapshot();
		});

	test("pins discovery files", async () => {
		for (const path of ["/robots.txt", "/llms.txt", "/sitemap.xml"])
			expect(await (await get(path)).text()).toMatchSnapshot();
	});
});

describe("search metadata", () => {
	test("landing page", async () => {
		const found = head(await (await get("/welcome")).text());
		expect(found.title).toBe(
			"Nigeria&#39;s Constitution and published laws | constitution.ng",
		);
		expect(found.canonical).toBe(`${origin}/welcome`);
		expect(found.schema.map((item) => item["@type"])).toEqual([
			"FAQPage",
			"WebSite",
			"WebPage",
		]);
		const page = found.schema[2];
		expect(page.url).toBe(`${origin}/welcome`);
		expect(page.name).toBe(
			"Nigeria's Constitution and published laws | constitution.ng",
		);
		expect(found.meta).toContain(
			'<meta data-public-head name="robots" content="index, follow">',
		);
	});
	test("about and methodology", async () => {
		for (const [path, title] of [
			["/about", "About, sources and corrections | constitution.ng"],
			["/methodology", "Retrieval test and methodology | constitution.ng"],
		]) {
			const found = head(await (await get(path)).text());
			expect(found.title).toBe(title);
			expect(found.canonical).toBe(origin + path);
			expect(found.schema.map((item) => item["@type"])).toEqual([
				"WebSite",
				"WebPage",
			]);
		}
	});
	test("browse and provision pages", async () => {
		const browse = head(
			await (
				await get(`/laws/constitution-1999?release=${release}`)
			).text(),
		);
		expect(browse.title).toBe(
			"Browse Constitution | source edition | constitution.ng",
		);
		expect(browse.canonical).toBe(
			`${origin}/laws/constitution-1999?release=${release}`,
		);
		expect(browse.schema.map((item) => item["@type"])).toEqual(["WebPage"]);
		const reading = head(
			await (
				await get(`/laws/constitution-1999/${sectionPath}?release=${release}`)
			).text(),
		);
		expect(reading.title).toBe(
			"Section 37: Right to private and family life | 2004 source edition | constitution.ng",
		);
		expect(reading.canonical).toBe(
			`${origin}/laws/constitution-1999/${sectionPath}?release=${release}`,
		);
		expect(reading.schema.map((item) => item["@type"])).toEqual([
			"WebSite",
			"WebPage",
			"BreadcrumbList",
		]);
	});
	test("sitemap entries", async () => {
		const xml = await (await get("/sitemap.xml")).text();
		const locs = [...xml.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]);
		expect(locs).toEqual([
			`${origin}/welcome`,
			`${origin}/about`,
			`${origin}/methodology`,
			`${origin}/laws/constitution-1999?release=${release}`,
			`${origin}/laws/constitution-1999?parent=constitution-1999.chapter4&amp;release=${release}`,
			`${origin}/laws/constitution-1999/${sectionPath}?release=${release}`,
		]);
	});
	test("corpus text with replacement patterns is rendered literally", async () => {
		const text = "Pay $& then $' and $1 and $$";
		const html = await (
			await get(
				`/laws/constitution-1999/${sectionPath}?release=${release}`,
				async () => Response.json({ data: [{ ...provision, authoritative_text: text }] }),
			)
		).text();
		expect(html).toContain("Pay $&amp; then $&#39; and $1 and $$");
	});
	test("an absent or unsafe site origin fails closed", async () => {
		for (const PUBLIC_SITE_URL of [
			undefined,
			"",
			"http://example.test",
			"https://user:secret@example.test",
			"https://example.test/path",
		]) {
			const response = await handleRequest(
				new Request(`${origin}/welcome`),
				{ ...env, PUBLIC_SITE_URL },
				backend,
			);
			expect(response.status).toBe(503);
			expect(response.headers.get("x-robots-tag")).toBe("noindex");
		}
	});
});
