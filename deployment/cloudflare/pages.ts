import type {
	LegalInstrumentPublic,
	ProvisionReference,
	ProvisionTreePublic,
	LegalSearchResult,
} from "../../frontend/src/client/types.gen";
import {
	editionName,
	editionNote,
	lawName,
	readableText,
} from "../../frontend/src/lib/legal-provisions";
import { faqs, LANDING_HEADLINE } from "../../frontend/src/lib/public-pages";
import {
	browsePath,
	CORRECTIONS_LABEL,
	CORRECTIONS_URL,
	EDITION_CAVEAT,
	publicPages,
	referencePath,
	SITE_DESCRIPTION,
	type SeoMetadata,
} from "../../frontend/src/lib/seo";
import { Html, html, joined, json, raw } from "./html";

// Tailwind classes shared by the page bodies. The built stylesheet that the
// asset shell links already contains them.
const textClass = "mt-4 text-body-lg leading-7";
const linkClass = "text-primary underline";
const headingClass = "mt-8 font-display text-title-3";
const titleClass = "mt-8 font-display text-title-2";

export function anchor(path: string, label: string): Html {
	return html`<a class="${linkClass}" href="${path}">${label}</a>`;
}

export function safeSource(value: string | null | undefined, origin: string) {
	if (!value) return null;
	try {
		const url = new URL(value, origin);
		return ["https:", "http:"].includes(url.protocol) ? url.href : null;
	} catch {
		return null;
	}
}

export function documentPath(node: ProvisionReference, release: string) {
	return node.has_text
		? referencePath(node.canonical_path, release)
		: browsePath(node.canonical_path, release);
}

function referenceList(nodes: ProvisionReference[], release: string): Html {
	return html`<ul class="mt-5 grid gap-3">${nodes.map(
		(node) =>
			html`<li class="sq-md border border-border bg-card p-4">${anchor(
				documentPath(node, release),
				`${node.citation}${node.title ? `: ${node.title}` : ""}`,
			)}</li>`,
	)}</ul>`;
}

/** Navigation and footer around every public page body. */
export function layout(body: Html): Html {
	return html`
		<main class="mx-auto max-w-4xl px-4 py-8 sm:px-8">
			<nav aria-label="Public navigation" class="flex flex-wrap gap-4 text-sm">
				${anchor("/welcome", "constitution.ng")}
				${" "}${anchor("/laws", "Browse published laws")}
				${" "}${anchor("/about", "Sources and corrections")}
			</nav>
			${body}
			<footer class="mt-8 border-t border-border py-8 text-sm">
				${anchor("/about", "About constitution.ng")} · 
				${anchor("/methodology", "Retrieval methodology")} · 
				${anchor(CORRECTIONS_URL, CORRECTIONS_LABEL)}
				<p class="mt-4">Independent. Not a government publication. Explanations are not legal advice.</p>
			</footer>
		</main>
	`;
}

/** `<head>` elements the browser app takes over once it is ready to mount. */
export function head(metadata: SeoMetadata): Html {
	const tag = (name: string, content: string, property = false) =>
		html`<meta data-public-head ${raw(property ? "property" : "name")}="${name}" content="${content}">`;
	return html`
		<title data-public-head>${metadata.title}</title>
		${tag("description", metadata.description)}
		${tag("robots", metadata.index ? "index, follow" : "noindex, follow")}
		${tag("og:type", "website", true)}
		${tag("og:site_name", "constitution.ng", true)}
		${tag("og:title", metadata.title, true)}
		${tag("og:description", metadata.description, true)}
		${
			metadata.canonical &&
			html`
				<link data-public-head rel="canonical" href="${metadata.canonical}">
				${tag("og:url", metadata.canonical, true)}
			`
		}
		${tag("twitter:card", "summary")}
		${(metadata.schema ?? []).map(
			(schema) =>
				html`<script data-public-head type="application/ld+json">${raw(json(schema))}</script>`,
		)}
	`;
}

export function landingBody(): Html {
	return html`
		<h1 class="mt-8 font-display text-title-1">${LANDING_HEADLINE}</h1>
		<p class="${textClass}">${SITE_DESCRIPTION}</p>
		<p class="${textClass}">${EDITION_CAVEAT}</p>
		<form action="/" method="get" class="mt-8">
			<label for="public-question">Your question about published laws</label>
			<input id="public-question" name="q" required maxlength="2000" class="sq-md mt-4 block w-full border border-border bg-card p-4">
			<input type="hidden" name="intent" value="find">
			<button class="sq-sm mt-4 bg-primary px-4 py-2 text-primary-foreground" type="submit">Find a section</button>
		</form>
		<h2 class="${headingClass}">Read the original wording</h2>
		<ul class="mt-4 grid gap-3">
			<li>${anchor("/constitution/constitution-1999.chapter4.section37", "Section 37: Right to private and family life")}</li>
			<li>${anchor("/constitution/constitution-1999.chapter4.section35", "Section 35: Right to personal liberty")}</li>
			<li>${anchor("/laws", "Browse published laws, sections and schedules")}</li>
		</ul>
		<h2 class="${headingClass}">Check every answer against its source</h2>
		<p class="${textClass}">Questions can be phrased in English or Pidgin; explanations are in English. Read the cited source wording and its edition before relying on an explanation. The source edition has known gaps and does not include later amendments.</p>
		<p class="${textClass}">${anchor("/methodology", "Read the dated retrieval test and its limits")} and ${anchor("/about", "how sources, review and corrections work")}.</p>
		<h2 class="${headingClass}">Before you ask</h2>
		${faqs.map(
			(item) => html`
				<details class="mt-4">
					<summary>${item.q}</summary>
					<p class="${textClass}">${item.a}</p>
				</details>
			`,
		)}
	`;
}

export function staticPageBody(path: keyof typeof publicPages): Html {
	const page = publicPages[path];
	return html`
		<h1 class="${titleClass}">${page.heading}</h1>
		${page.sections.map(
			(section) => html`
				<section>
					<h2 class="${headingClass}">${section.heading}</h2>
					<p class="${textClass}">${section.text}</p>
				</section>
			`,
		)}
		<p class="${textClass}">${anchor("/methodology/benchmark.json", "Versioned retrieval test")}</p>
	`;
}

export function treeBody(
	laws: LegalInstrumentPublic[],
	law: LegalInstrumentPublic,
	tree: ProvisionTreePublic,
	instrument: string,
	parent: string | undefined,
): Html {
	const name = law.short_title || law.title;
	const heading = tree.parent
		? `${tree.parent.citation}: ${tree.parent.title || tree.parent.heading || "Published provisions"}`
		: `Browse ${name}`;
	return html`
		<nav aria-label="Published laws" class="mt-8 flex flex-wrap gap-3">${joined(
			laws.map((item) =>
				anchor(
					browsePath(undefined, tree.release_version, item.slug),
					item.short_title || item.title,
				),
			),
			" · ",
		)}</nav>
		<h1 class="${titleClass}">${heading}</h1>
		<p class="${textClass}">${tree.edition_label}. ${law.edition_note}</p>
		${
			parent &&
			html`<p class="${textClass}">${anchor(browsePath(undefined, tree.release_version, instrument), "All parts and sections")}</p>`
		}
		${referenceList(tree.data, tree.release_version)}
	`;
}

export function provisionBody(
	provision: LegalSearchResult,
	source: string | null,
): Html {
	const pages = provision.source_page_start
		? ` · printed page ${provision.source_page_start}${
				provision.source_page_end &&
				provision.source_page_end !== provision.source_page_start
					? `–${provision.source_page_end}`
					: ""
			}`
		: "";
	return html`
		<nav aria-label="Provision hierarchy" class="mt-8 flex flex-wrap gap-3">${joined(
			provision.ancestors.map((node) =>
				anchor(documentPath(node, provision.release_version), node.citation),
			),
			" · ",
		)}</nav>
		<h1 class="${titleClass}">${provision.title || provision.citation}</h1>
		<p class="${textClass}">${provision.citation} · ${editionName(provision.edition_label, provision)}</p>
		<h2 class="${headingClass}">What ${lawName(provision)} says</h2>
		<p class="mt-4 whitespace-pre-wrap font-legal text-statute">${readableText(provision.authoritative_text)}</p>
		<p class="${textClass}">${provision.legal_status === "historical" ? editionNote(provision.edition_label, provision) : provision.edition_label}</p>
		<h2 class="${headingClass}">Original source</h2>
		<p class="${textClass}">${provision.source_authority} · ${provision.source_title}${pages}. ${source && anchor(source, "Original document")}</p>
		<p class="${textClass}">Release: ${provision.release_version}. ${anchor("/about", "Source scope, review and corrections")}</p>
		${
			provision.children.length > 0 &&
			html`
				<h2 class="${headingClass}">Within this provision</h2>
				${referenceList(provision.children, provision.release_version)}
			`
		}
	`;
}

export function amendmentsBody(): Html {
	return html`
		<h1 class="${titleClass}">Amendments are not published here yet</h1>
		<p class="${textClass}">Reviewed amendment records and comparisons are not available. ${anchor("/constitution", "Browse the historical source edition")}.</p>
	`;
}

/** What a visitor without JavaScript sees on app-only routes. */
export function utilityBody(): Html {
	return html`
		<h1 class="${titleClass}">constitution.ng</h1>
		<p class="${textClass}">Open the interactive application with JavaScript enabled. ${anchor("/constitution", "Read the public source edition")}.</p>
	`;
}

export function errorBody(title: string, status: number): Html {
	const message =
		status === 503
			? "Please try again shortly. The source could not be checked, so this response does not assert that the provision is missing."
			: "This page is not available.";
	return html`
		<h1 class="${titleClass}">${title}</h1>
		<p class="${textClass}">${message} ${anchor("/constitution", "Browse published provisions")}.</p>
	`;
}
