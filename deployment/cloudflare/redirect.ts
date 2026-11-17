interface Env { PUBLIC_SITE_URL: string }

export default {
  fetch(request: Request, env: Env): Response {
    let destination: URL
    try {
      destination = new URL(env.PUBLIC_SITE_URL)
    } catch {
      return new Response("Invalid redirect configuration", { status: 500 })
    }
    if (destination.protocol !== "https:" || destination.username || destination.password || destination.pathname !== "/" || destination.search || destination.hash) {
      return new Response("Invalid redirect configuration", { status: 500 })
    }
    const incoming = new URL(request.url)
    destination.pathname = incoming.pathname
    destination.search = incoming.search
    return Response.redirect(destination.toString(), 308)
  },
}
