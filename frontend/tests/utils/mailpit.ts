import { type APIRequestContext, expect } from "@playwright/test"

type EmailSummary = {
  ID: string
}

/** Wait for the newest email matching a Mailpit search and return its HTML. */
export async function waitForEmailHtml({
  request,
  query,
  timeout = 5000,
}: {
  request: APIRequestContext
  query: string
  timeout?: number
}) {
  let email: EmailSummary | undefined

  await expect(async () => {
    const response = await request.get(
      `${process.env.MAILPIT_HOST}/api/v1/search`,
      { params: { query, limit: 1 } },
    )
    expect(response.ok()).toBe(true)
    const { messages }: { messages: EmailSummary[] } = await response.json()
    email = messages[0]
    expect(email).toBeDefined()
  }, `No email found for "${query}"`).toPass({ timeout, intervals: [100] })

  const htmlResponse = await request.get(
    `${process.env.MAILPIT_HOST}/view/${email?.ID}.html`,
  )
  if (!htmlResponse.ok()) {
    throw new Error(
      `Could not get the HTML for email "${email?.ID}": ${htmlResponse.status()}`,
    )
  }

  return htmlResponse.text()
}
