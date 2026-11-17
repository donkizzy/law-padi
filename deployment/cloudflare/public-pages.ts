import type {
	LegalInstrumentsPublic,
	LegalSearchResponse,
	LegalSearchResult,
	ProvisionTreePublic,
} from "../../frontend/src/client/types.gen";
import { publicBenchmark } from "../../frontend/src/lib/public-content";
import {
	amendmentsMetadata,
	landingMetadata,
	staticPageMetadata,
} from "../../frontend/src/lib/public-pages";
import {
	browsePath,
	EDITION_CAVEAT,
	pageSchema,
	provisionMetadata,
	publicPages,
	referencePath,
	SITE_DESCRIPTION,
	siteOrigin,
	type SeoMetadata,
} from "../../frontend/src/lib/seo";
import { escapeHtml, type Html, html, json, raw } from "./html";
import {
	amendmentsBody,
	documentPath,
	errorBody,
	head,
	landingBody,
	layout,
	provisionBody,
	safeSource,
	staticPageBody,
	treeBody,
	utilityBody,
} from "./pages";

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
async function htmlResponse(
	request: Request,
	env: PublicEnv,
	metadata: SeoMetadata,
	body: Html,
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
		.replace("</head>", () => `${head(metadata)}</head>`)
		.replace(
			'<div id="root"></div>',
			// A function replacer keeps `$&` and similar sequences in corpus text literal.
			() =>
				html`<div id="root">${layout(body)}</div>${
					bootstrap
						? html`<script id="public-corpus-data" type="application/json">${raw(json(bootstrap))}</script>`
						: ""
				}`.value,
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
		// No configured origin is an error: the Worker never guesses a canonical host.
		origin = siteOrigin(env.PUBLIC_SITE_URL ?? "");
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
			return htmlResponse(
				request,
				env,
				{ ...landingMetadata(origin), index: canIndex },
				landingBody(),
			);
		}
		if (path in publicPages) {
			const page = path as keyof typeof publicPages;
			return htmlResponse(
				request,
				env,
				{ ...staticPageMetadata(page, origin), index: canIndex },
				staticPageBody(page),
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
				treeBody(instruments.data, law, tree, instrument, parent),
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
			return htmlResponse(
				request,
				env,
				{ ...metadata, index: canIndex },
				provisionBody(provision, source),
				200,
				{ kind: "provision", path: provisionPath, release, data: provision },
			);
		}
		if (path === "/amendments")
			return htmlResponse(
				request,
				env,
				amendmentsMetadata,
				amendmentsBody(),
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
				utilityBody(),
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
			errorBody(title, status),
			status,
		);
	}
}
