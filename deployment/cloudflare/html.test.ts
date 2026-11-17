import { describe, expect, test } from "bun:test";
import { escapeHtml, html, joined, json, raw } from "./html";

describe("html template", () => {
	test("escapes interpolated text but not nested markup", () => {
		const inner = html`<b>${"<i>"}</b>`;
		expect(html`<p title="${'"x"'}">${inner}${"a&b"}</p>`.value).toBe(
			'<p title="&quot;x&quot;"><b>&lt;i&gt;</b>a&amp;b</p>',
		);
	});
	test("drops layout whitespace in static parts only", () => {
		const text = "line one\n    line two";
		expect(
			html`
				<p>
					${text}
				</p>
			`.value,
		).toBe(`<p>${text}</p>`);
	});
	test("renders lists and omits empty values", () => {
		expect(html`${[html`<i>1</i>`, "<2>"]}${null}${undefined}${false}${0}`.value).toBe(
			"<i>1</i>&lt;2&gt;0",
		);
		expect(joined([raw("a"), raw("b")], " · ").value).toBe("a · b");
	});
	test("keeps inline JSON from closing its script", () => {
		expect(json({ a: "</script>\u2028" })).toBe(
			'{"a":"\\u003c/script>\\u2028"}',
		);
		expect(escapeHtml(`<'">&`)).toBe("&lt;&#39;&quot;&gt;&amp;");
	});
});
