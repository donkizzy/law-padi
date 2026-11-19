import { expect } from "bun:test";
import { handleRequest } from "./worker";

export const origin = "https://example.test";
export const sectionPath = "constitution-1999.chapter4.section37";
export const chapter = {
	id: "chapter",
	canonical_path: "constitution-1999.chapter4",
	kind: "chapter",
	citation: "Chapter 4",
	title: "Fundamental rights",
	has_text: false,
};
export const section = {
	id: "section",
	canonical_path: sectionPath,
	kind: "section",
	citation: "Section 37",
	title: "Right to private and family life",
	has_text: true,
};
export const provision = {
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
export const shell =
	'<!DOCTYPE html><html lang="en"><head><title>old title</title><meta name="description" content="old description"></head><body><div id="root"></div><script src="/assets/index-Abcdef12.js"></script></body></html>';
export const env = {
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
	API_ORIGIN: "https://constitution-ng-api.up.railway.app",
	ORIGIN_PROXY_SECRET: "test-secret",
	PUBLIC_SITE_URL: origin,
};
export const instruments = {
	data: [
		{
			slug: "constitution-1999",
			title: "Constitution",
			short_title: "Constitution",
			edition_label: provision.edition_label,
			edition_note: "Later amendments are not included.",
		},
	],
	release_version: provision.release_version,
	count: 1,
};
export function backend(request: Request): Promise<Response> {
	const url = new URL(request.url);
	expect(request.headers.get("cookie")).toBeNull();
	expect(request.headers.get("authorization")).toBeNull();
	expect(request.headers.get("x-origin-proxy-secret")).toBe("test-secret");
	if (url.pathname.endsWith("/instruments"))
		return Promise.resolve(Response.json(instruments));
	if (url.pathname.endsWith("/tree"))
		return Promise.resolve(
			Response.json({
				instrument_slug: "constitution-1999",
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
export function get(path: string, fetcher = backend, method = "GET") {
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

