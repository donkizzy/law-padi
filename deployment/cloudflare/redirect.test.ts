import { describe, expect, test } from "bun:test"
import redirect from "./redirect"

describe("legacy Worker redirect", () => {
  test("preserves the path and query on the configured HTTPS origin", () => {
    const response = redirect.fetch(
      new Request("https://old.example/laws/act?release=v1"),
      { PUBLIC_SITE_URL: "https://new.example" },
    )
    expect(response.status).toBe(308)
    expect(response.headers.get("location")).toBe("https://new.example/laws/act?release=v1")
  })

  test("rejects an invalid destination", () => {
    const response = redirect.fetch(new Request("https://old.example/"), {
      PUBLIC_SITE_URL: "http://new.example/path",
    })
    expect(response.status).toBe(500)
  })
})
