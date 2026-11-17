/**
 * A tiny escaping template for the Worker's HTML.
 *
 * Interpolated values are escaped unless they are already `Html`, so a page
 * template cannot emit corpus text unescaped by omission. Line breaks and
 * indentation in the static parts are dropped, which lets templates be laid out
 * as readable markup without changing the HTML sent to crawlers.
 */
export class Html {
	constructor(readonly value: string) {}
	toString() {
		return this.value;
	}
}

const ESCAPES: Record<string, string> = {
	"&": "&amp;",
	"<": "&lt;",
	">": "&gt;",
	'"': "&quot;",
	"'": "&#39;",
};

export function escapeHtml(value: unknown): string {
	return String(value ?? "").replace(/[&<>"']/g, (char) => ESCAPES[char]!);
}

/** JSON for an inline script: `<` and the JS line separators cannot end it early. */
export function json(value: unknown): string {
	return JSON.stringify(value)
		.replace(/</g, "\\u003c")
		.replace(/\u2028/g, "\\u2028")
		.replace(/\u2029/g, "\\u2029");
}

export type Interpolation = Html | string | number | null | undefined | false | Interpolation[];

function render(value: Interpolation): string {
	if (value instanceof Html) return value.value;
	if (Array.isArray(value)) return value.map(render).join("");
	if (value === null || value === undefined || value === false) return "";
	return escapeHtml(value);
}

export function html(
	strings: TemplateStringsArray,
	...values: Interpolation[]
): Html {
	let out = "";
	strings.forEach((part, index) => {
		out += part.replace(/\n\s*/g, "");
		if (index < values.length) out += render(values[index]);
	});
	return new Html(out);
}

/** Marks trusted markup, such as an inline JSON script, as already safe. */
export function raw(value: string): Html {
	return new Html(value);
}

/** Joins items with a literal separator. */
export function joined(items: Html[], separator: string): Html {
	return new Html(items.map((item) => item.value).join(separator));
}
