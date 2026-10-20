import { faqs, publicBenchmark } from "../../frontend/src/lib/public-content";
import type {
	LegalInstrumentsPublic,
	LegalSearchResponse,
	LegalSearchResult,
	ProvisionReference,
	ProvisionTreePublic,
} from "../../frontend/src/client/types.gen";
import {
	editionName,
	editionNote,
	lawName,
	readableText,
} from "../../frontend/src/lib/legal-provisions";
import {
	browsePath,
	CORRECTIONS_URL,
	DEFAULT_SITE_URL,
	EDITION_CAVEAT,
	pageSchema,
	provisionMetadata,
	publicPages,
	referencePath,
	SITE_DESCRIPTION,
	siteOrigin,
	type SeoMetadata,
	websiteSchema,
} from "../../frontend/src/lib/seo";

export interface PublicEnv {
	ASSETS: { fetch(request: Request): Promise<Response> };
	PUBLIC_SITE_URL?: string;
}
type ReadApi = (path: string) => Promise<Response>;
const utilities = new Set([
	"/login",
	"/signup",
	"/recover-password",
	"/reset-password",
	"/verify-email",
	"/saved",
	"/settings",
	"/admin",
	"/privacy",
]);
const textClass = "mt-4 text-body-lg leading-7";
const linkClass = "text-primary underline";
const headingClass = "mt-8 font-display text-title-3";

export function escapeHtml(value: unknown): string {
	return String(value ?? "").replace(
		/[&<>"']/g,
		(char) =>
			({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
				char
			]!,
	);
}
function json(value: unknown) {
	return JSON.stringify(value)
		.replace(/</g, "\\u003c")
		.replace(/\u2028/g, "\\u2028")
		.replace(/\u2029/g, "\\u2029");
}
function anchor(path: string, label: string) {
	return `<a class="${linkClass}" href="${escapeHtml(path)}">${escapeHtml(label)}</a>`;
}
function safeSource(value: string | null | undefined, origin: string) {
	if (!value) return null;
	try {
		const url = new URL(value, origin);
		return ["https:", "http:"].includes(url.protocol) ? url.href : null;
	} catch {
		return null;
	}
}
function documentPath(node: ProvisionReference, release: string) {
	return node.has_text
		? referencePath(node.canonical_path, release)
		: browsePath(node.canonical_path, release);
}
function referenceList(nodes: ProvisionReference[], release: string) {
	return `<ul class="mt-5 grid gap-3">${nodes.map((node) => `<li class="sq-md border border-border bg-card p-4">${anchor(documentPath(node, release), `${node.citation}${node.title ? `: ${node.title}` : ""}`)}</li>`).join("")}</ul>`;
}
function layout(body: string) {
	return `<main class="mx-auto max-w-4xl px-4 py-8 sm:px-8"><nav aria-label="Public navigation" class="flex flex-wrap gap-4 text-sm">${anchor("/welcome", "constitution.ng")} ${anchor("/laws", "Browse published laws")} ${anchor("/about", "Sources and corrections")}</nav>${body}<footer class="mt-8 border-t border-border py-8 text-sm">${anchor("/about", "About constitution.ng")} · ${anchor("/methodology", "Retrieval methodology")} · ${anchor(CORRECTIONS_URL, "Corrections on GitHub (repository access required)")}<p class="mt-4">Independent. Not a government publication. Explanations are not legal advice.</p></footer></main>`;
}
function staticPage(path: keyof typeof publicPages, origin: string) {
	const page = publicPages[path];
	const canonical = origin + path;
	const body = `<h1 class="mt-8 font-display text-title-2">${escapeHtml(page.heading)}</h1>${page.sections.map((section) => `<section><h2 class="${headingClass}">${escapeHtml(section.heading)}</h2><p class="${textClass}">${escapeHtml(section.text)}</p></section>`).join("")}<p class="${textClass}">${anchor("/methodology/benchmark.json", "Versioned retrieval test")}</p>`;
	return {
		body,
		metadata: {
			title: page.title,
			description: page.description,
			canonical,
			index: true,
			schema: [
				websiteSchema(origin),
				pageSchema(page.title, canonical, page.description),
			],
		},
	};
}
function landing(origin: string) {
	const title = "Nigeria's Constitution and published laws | constitution.ng";
	const canonical = `${origin}/welcome`;
	const body = `<h1 class="mt-8 font-display text-title-1">Ask about your rights. Get the exact section.</h1><p class="${textClass}">${escapeHtml(SITE_DESCRIPTION)}</p><p class="${textClass}">${escapeHtml(EDITION_CAVEAT)}</p><form action="/" method="get" class="mt-8"><label for="public-question">Your question about published laws</label><input id="public-question" name="q" required maxlength="2000" class="sq-md mt-4 block w-full border border-border bg-card p-4"><input type="hidden" name="intent" value="find"><button class="sq-sm mt-4 bg-primary px-4 py-2 text-primary-foreground" type="submit">Find a section</button></form><h2 class="${headingClass}">Read the original wording</h2><ul class="mt-4 grid gap-3"><li>${anchor("/constitution/constitution-1999.chapter4.section37", "Section 37: Right to private and family life")}</li><li>${anchor("/constitution/constitution-1999.chapter4.section35", "Section 35: Right to personal liberty")}</li><li>${anchor("/laws", "Browse published laws, sections and schedules")}</li></ul><h2 class="${headingClass}">Check every answer against its source</h2><p class="${textClass}">Questions can be phrased in English or Pidgin; explanations are in English. Read the cited source wording and its edition before relying on an explanation. The source edition has known gaps and does not include later amendments.</p><p class="${textClass}">${anchor("/methodology", "Read the dated retrieval test and its limits")} and ${anchor("/about", "how sources, review and corrections work")}.</p>`;
	return {
		body:
			body +
			`<h2 class="${headingClass}">Before you ask</h2>${faqs.map((item) => `<details class="mt-4"><summary>${escapeHtml(item.q)}</summary><p class="${textClass}">${escapeHtml(item.a)}</p></details>`).join("")}`,
		metadata: {
			title,
			description: SITE_DESCRIPTION,
			canonical,
			index: true,
			schema: [
				{
					"@context": "https://schema.org",
					"@type": "FAQPage",
					mainEntity: faqs.map((item) => ({
						"@type": "Question",
						name: item.q,
						acceptedAnswer: { "@type": "Answer", text: item.a },
					})),
				},
				websiteSchema(origin),
				pageSchema(title, canonical, SITE_DESCRIPTION),
			],
		},
	};
}
class PublicError extends Error {
	constructor(public status: number) {
		super("Public document unavailable");
	}
}
async function apiJson<T>(readApi: ReadApi, path: string): Promise<T> {
	const response = await readApi(path);
	if (!response.ok)
		throw new PublicError(
			response.status === 404 ? 404 : response.status === 422 ? 400 : 503,
		);
	try {
		return (await response.json()) as T;
	} catch {
		throw new PublicError(503);
	}
}
function treePath(
	parent?: string,
	release?: string,
	all = false,
	instrument = "constitution-1999",
) {
	const query = new URLSearchParams({ index_kind: "enacted" });
	if (parent) query.set("parent_path", parent);
	if (release) query.set("release_version", release);
	if (all) query.set("all_nodes", "true");
	query.set("instrument", instrument);
	return `/api/v1/legal/provisions/tree?${query}`;
}
function validateTree(tree: ProvisionTreePublic) {
	if (!Array.isArray(tree.data) || !tree.release_version || !tree.edition_label)
		throw new PublicError(503);
}
function head(metadata: SeoMetadata) {
	const tag = (name: string, content: string, property = false) =>
		`<meta data-public-head ${property ? "property" : "name"}="${name}" content="${escapeHtml(content)}">`;
	return `<title data-public-head>${escapeHtml(metadata.title)}</title>${tag("description", metadata.description)}${tag("robots", metadata.index ? "index, follow" : "noindex, follow")}${tag("og:type", "website", true)}${tag("og:site_name", "constitution.ng", true)}${tag("og:title", metadata.title, true)}${tag("og:description", metadata.description, true)}${metadata.canonical ? `<link data-public-head rel="canonical" href="${escapeHtml(metadata.canonical)}">${tag("og:url", metadata.canonical, true)}` : ""}${tag("twitter:card", "summary")}${(metadata.schema ?? []).map((schema) => `<script data-public-head type="application/ld+json">${json(schema)}</script>`).join("")}`;
}
async function htmlResponse(
	request: Request,
	env: PublicEnv,
	metadata: SeoMetadata,
	body: string,
	status = 200,
	bootstrap?: unknown,
) {
	const asset = await env.ASSETS.fetch(
		new Request(new URL("/", request.url), { method: "GET" }),
	);
	if (!asset.ok)
		return new Response("Site temporarily unavailable", {
			status: 503,
			headers: { "x-robots-tag": "noindex", "retry-after": "60" },
		});
	let shell = await asset.text();
	// The shell is a build artifact, never personalized HTML. Browser HeadContent
	// takes over these marked tags only after the app is ready to mount.
	shell = shell
		.replace(/<title\b[^>]*>[\s\S]*?<\/title>/gi, "")
		.replace(/<meta\b[^>]*name=["'](?:description|robots)["'][^>]*>/gi, "");
	shell = shell
		.replace("</head>", `${head(metadata)}</head>`)
		.replace(
			'<div id="root"></div>',
			`<div id="root">${layout(body)}</div>${bootstrap ? `<script id="public-corpus-data" type="application/json">${json(bootstrap)}</script>` : ""}`,
		);
	const headers = new Headers({
		"content-type": "text/html; charset=utf-8",
		"cache-control": "private, no-store",
		"x-robots-tag": metadata.index ? "index, follow" : "noindex, follow",
	});
	if (metadata.canonical)
		headers.set("link", `<${metadata.canonical}>; rel="canonical"`);
	if (status === 503) headers.set("retry-after", "60");
	return new Response(request.method === "HEAD" ? null : shell, {
		status,
		headers,
	});
}
function plain(request: Request, body: string, type: string, status = 200) {
	return new Response(request.method === "HEAD" ? null : body, {
		status,
		headers: {
			"content-type": `${type}; charset=utf-8`,
			"cache-control": status >= 400 ? "no-store" : "public, max-age=300",
			...(status >= 400 ? { "x-robots-tag": "noindex" } : {}),
			...(status === 503 ? { "retry-after": "60" } : {}),
			"x-content-type-options": "nosniff",
		},
	});
}
function searchRobots(origin: string) {
	// Search access and model training are separate. These rules do not add a
	// new training preference or grant access to authenticated data.
	return `User-agent: *\nUser-agent: OAI-SearchBot\nUser-agent: Claude-SearchBot\nUser-agent: PerplexityBot\nAllow: /\nDisallow: /api/\n\nSitemap: ${origin}/sitemap.xml\n`;
}
function llmsDirectory(origin: string) {
	return `# constitution.ng\n\n> Independent Nigerian legal reference. Published source editions, not certified current consolidated law.\n\n${EDITION_CAVEAT}\n\n## Reading and provenance\n- [Browse the source edition](${origin}/laws): Law and provision links, pinned to the published release.\n- [Sources and corrections](${origin}/about): Publisher, review boundaries, known corpus gaps and corrections.\n- [Retrieval methodology](${origin}/methodology): Dated retrieval benchmark; not a measure of answer correctness.\n\n## Citation guidance\nCite a provision's release-pinned canonical URL, edition, citation and original source. Do not describe historical wording as current consolidated law. Explanations are not legal advice.\n`;
}
export async function publicRequest(
	request: Request,
	env: PublicEnv,
	readApi: ReadApi,
): Promise<Response> {
	const url = new URL(request.url);
	let origin: string;
	try {
		origin = siteOrigin(env.PUBLIC_SITE_URL ?? DEFAULT_SITE_URL);
	} catch {
		return new Response("Public origin configuration unavailable", {
			status: 503,
			headers: { "x-robots-tag": "noindex" },
		});
	}
	if (!["GET", "HEAD"].includes(request.method))
		return new Response("Method not allowed", {
			status: 405,
			headers: { allow: "GET, HEAD" },
		});
	const path = url.pathname.replace(/\/$/, "") || "/";
	if (path === "/methodology/benchmark.json")
		return plain(request, json(publicBenchmark), "application/json");
	if (path === "/robots.txt")
		return plain(request, searchRobots(origin), "text/plain");
	if (path === "/llms.txt")
		return plain(request, llmsDirectory(origin), "text/plain");
	if (path === "/sitemap.xml") {
		try {
			const instruments = await apiJson<LegalInstrumentsPublic>(
				readApi,
				"/api/v1/legal/instruments",
			);
			if (!instruments.release_version || !instruments.data?.length)
				throw new PublicError(503);
			const trees = await Promise.all(
				instruments.data.map(async (law) => {
					const tree = await apiJson<ProvisionTreePublic>(
						readApi,
						treePath(undefined, instruments.release_version, true, law.slug),
					);
					validateTree(tree);
					if (
						tree.scope !== "all" ||
						tree.release_version !== instruments.release_version ||
						tree.instrument_slug !== law.slug ||
						tree.data.some(
							(node) => !node.canonical_path.startsWith(law.slug + "."),
						)
					)
						throw new PublicError(503);
					return tree;
				}),
			);
			const paths = new Set(["/welcome", "/about", "/methodology"]);
			for (const tree of trees) {
				paths.add(
					browsePath(undefined, tree.release_version, tree.instrument_slug),
				);
				for (const node of tree.data)
					if (!["subsection", "paragraph"].includes(node.kind))
						paths.add(documentPath(node, tree.release_version));
			}
			if (paths.size > 50000) throw new PublicError(503);
			const xml = `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${[...paths].map((item) => `<url><loc>${escapeHtml(origin + item)}</loc></url>`).join("")}</urlset>`;
			return plain(request, xml, "application/xml");
		} catch {
			return plain(
				request,
				"Sitemap temporarily unavailable",
				"text/plain",
				503,
			);
		}
	}
	if (path.startsWith("/assets/")) {
		const response = await env.ASSETS.fetch(request);
		const headers = new Headers(response.headers);
		if (
			response.ok &&
			/[-.][a-zA-Z0-9_-]{8,}\.(?:js|css|woff2?|svg|png|webp)$/.test(path) &&
			!headers.get("content-type")?.includes("text/html")
		)
			headers.set("cache-control", "public, max-age=31536000, immutable");
		return new Response(request.method === "HEAD" ? null : response.body, {
			status: response.status,
			headers,
		});
	}
	const release = url.searchParams.get("release") ?? undefined;
	const parent = url.searchParams.get("parent") ?? undefined;
	const invalid =
		(release !== undefined && (release.length < 1 || release.length > 128)) ||
		(parent !== undefined && (parent.length < 1 || parent.length > 512));
	const canIndex =
		url.origin === origin &&
		[...url.searchParams.keys()].every((key) =>
			[
				"release",
				"parent",
				"utm_source",
				"utm_medium",
				"utm_campaign",
			].includes(key),
		);
	try {
		if (invalid) throw new PublicError(400);
		if (path === "/welcome" || (path === "/" && !url.search)) {
			const page = landing(origin);
			return htmlResponse(
				request,
				env,
				{ ...page.metadata, index: canIndex },
				page.body,
			);
		}
		if (path in publicPages) {
			const page = staticPage(path as keyof typeof publicPages, origin);
			return htmlResponse(
				request,
				env,
				{ ...page.metadata, index: canIndex },
				page.body,
			);
		}
		const lawRoute = path.match(
			/^\/laws\/([a-z0-9]+(?:-[a-z0-9]+)*)(?:\/(.+))?$/,
		);
		if (
			path === "/constitution" ||
			path === "/laws" ||
			(lawRoute && !lawRoute[2])
		) {
			const instrument = lawRoute?.[1] || "constitution-1999";
			const instruments = await apiJson<LegalInstrumentsPublic>(
				readApi,
				`/api/v1/legal/instruments${release ? `?${new URLSearchParams({ release_version: release })}` : ""}`,
			);
			const law = instruments.data?.find((item) => item.slug === instrument);
			if (!law) throw new PublicError(404);
			if (
				!instruments.release_version ||
				(release && instruments.release_version !== release)
			)
				throw new PublicError(503);
			const tree = await apiJson<ProvisionTreePublic>(
				readApi,
				treePath(parent, instruments.release_version, false, instrument),
			);
			validateTree(tree);
			if (
				tree.scope !== "children" ||
				tree.instrument_slug !== instrument ||
				(parent && tree.parent?.canonical_path !== parent) ||
				tree.data.some(
					(node) => !node.canonical_path.startsWith(instrument + "."),
				) ||
				tree.release_version !== instruments.release_version
			)
				throw new PublicError(503);
			if (!release || path === "/laws")
				return new Response(null, {
					status: 302,
					headers: {
						location:
							origin + browsePath(parent, tree.release_version, instrument),
						"cache-control": "no-store",
					},
				});
			const name = law.short_title || law.title;
			const title = `${tree.parent?.citation ?? `Browse ${name}`}${tree.parent?.title ? `: ${tree.parent.title}` : ""} | source edition | constitution.ng`;
			const canonical =
				origin + browsePath(parent, tree.release_version, instrument);
			const description = `Read the published parts and sections of ${name}. ${law.edition_note}`;
			const body = `<nav aria-label="Published laws" class="mt-8 flex flex-wrap gap-3">${instruments.data.map((item) => anchor(browsePath(undefined, tree.release_version, item.slug), item.short_title || item.title)).join(" · ")}</nav><h1 class="mt-8 font-display text-title-2">${escapeHtml(tree.parent ? `${tree.parent.citation}: ${tree.parent.title || tree.parent.heading || "Published provisions"}` : `Browse ${name}`)}</h1><p class="${textClass}">${escapeHtml(tree.edition_label)}. ${escapeHtml(law.edition_note)}</p>${parent ? `<p class="${textClass}">${anchor(browsePath(undefined, tree.release_version, instrument), "All parts and sections")}</p>` : ""}${referenceList(tree.data, tree.release_version)}`;
			return htmlResponse(
				request,
				env,
				{
					title,
					description,
					canonical,
					index: canIndex,
					schema: [pageSchema(title, canonical, description)],
				},
				body,
				200,
				{ kind: "tree", parent, release, instrument, data: tree },
			);
		}
		if (path.startsWith("/constitution/") || lawRoute?.[2]) {
			const provisionPath = decodeURIComponent(
				lawRoute?.[2] || path.slice("/constitution/".length),
			);
			if (
				!provisionPath ||
				!provisionPath.startsWith(`${lawRoute?.[1] || "constitution-1999"}.`) ||
				provisionPath.length > 512 ||
				/[\/\\\x00-\x1f]/.test(provisionPath)
			)
				throw new PublicError(404);
			const query = new URLSearchParams({ index_kind: "enacted" });
			if (release) query.set("release_version", release);
			const data = await apiJson<LegalSearchResponse>(
				readApi,
				`/api/v1/legal/provisions/${encodeURIComponent(provisionPath)}?${query}`,
			);
			const provision: LegalSearchResult | undefined = data.data?.[0];
			if (
				!provision ||
				provision.canonical_path !== provisionPath ||
				!provision.release_version ||
				typeof provision.authoritative_text !== "string"
			)
				throw new PublicError(404);
			if (release && provision.release_version !== release)
				throw new PublicError(503);
			if (!release)
				return new Response(null, {
					status: 302,
					headers: {
						location:
							origin + referencePath(provisionPath, provision.release_version),
						"cache-control": "no-store",
					},
				});
			const metadata = provisionMetadata(provision, origin);
			const source =
				safeSource(provision.source_url, origin) ??
				safeSource(provision.source_content_url, origin);
			const body = `<nav aria-label="Provision hierarchy" class="mt-8 flex flex-wrap gap-3">${provision.ancestors.map((node) => anchor(documentPath(node, provision.release_version), node.citation)).join(" · ")}</nav><h1 class="mt-8 font-display text-title-2">${escapeHtml(provision.title || provision.citation)}</h1><p class="${textClass}">${escapeHtml(provision.citation)} · ${escapeHtml(editionName(provision.edition_label, provision))}</p><h2 class="${headingClass}">What ${escapeHtml(lawName(provision))} says</h2><p class="mt-4 whitespace-pre-wrap font-legal text-statute">${escapeHtml(readableText(provision.authoritative_text))}</p><p class="${textClass}">${escapeHtml(provision.legal_status === "historical" ? editionNote(provision.edition_label, provision) : provision.edition_label)}</p><h2 class="${headingClass}">Original source</h2><p class="${textClass}">${escapeHtml(provision.source_authority)} · ${escapeHtml(provision.source_title)}${provision.source_page_start ? ` · printed page ${provision.source_page_start}${provision.source_page_end && provision.source_page_end !== provision.source_page_start ? `–${provision.source_page_end}` : ""}` : ""}. ${source ? anchor(source, "Original document") : ""}</p><p class="${textClass}">Release: ${escapeHtml(provision.release_version)}. ${anchor("/about", "Source scope, review and corrections")}</p>${provision.children.length ? `<h2 class="${headingClass}">Within this provision</h2>${referenceList(provision.children, provision.release_version)}` : ""}`;
			return htmlResponse(
				request,
				env,
				{ ...metadata, index: canIndex },
				body,
				200,
				{ kind: "provision", path: provisionPath, release, data: provision },
			);
		}
		if (path === "/amendments")
			return htmlResponse(
				request,
				env,
				{
					title: "Amendments unavailable | constitution.ng",
					description: "Reviewed amendment records are not published here yet.",
					index: false,
				},
				`<h1 class="mt-8 font-display text-title-2">Amendments are not published here yet</h1><p class="${textClass}">Reviewed amendment records and comparisons are not available. ${anchor("/constitution", "Browse the historical source edition")}.</p>`,
				410,
			);
		if (utilities.has(path) || path === "/")
			return htmlResponse(
				request,
				env,
				{
					title: "constitution.ng",
					description: SITE_DESCRIPTION,
					index: false,
				},
				`<h1 class="mt-8 font-display text-title-2">constitution.ng</h1><p class="${textClass}">Open the interactive application with JavaScript enabled. ${anchor("/constitution", "Read the public source edition")}.</p>`,
			);
		// Missing resources must not inherit the app shell's successful status.
		const asset = await env.ASSETS.fetch(request);
		if (asset.ok && !asset.headers.get("content-type")?.includes("text/html"))
			return asset;
		throw new PublicError(404);
	} catch (error) {
		const status =
			error instanceof PublicError
				? error.status
				: error instanceof URIError
					? 400
					: 503;
		const title =
			status === 404
				? "Page not found"
				: status === 400
					? "Invalid page request"
					: "Sources temporarily unavailable";
		return htmlResponse(
			request,
			env,
			{
				title: `${title} | constitution.ng`,
				description: SITE_DESCRIPTION,
				index: false,
			},
			`<h1 class="mt-8 font-display text-title-2">${title}</h1><p class="${textClass}">${status === 503 ? "Please try again shortly. The source could not be checked, so this response does not assert that the provision is missing." : "This page is not available."} ${anchor("/constitution", "Browse published provisions")}.</p>`,
			status,
		);
	}
}
