type WordedSource = {
  canonical_path: string
  authoritative_text: string
}

export function bestContainingSource<T extends WordedSource>(matches: T[]) {
  const first = matches[0]
  if (!first) return undefined
  const wording = first.authoritative_text.replace(/\s+/g, " ").trim()
  if (!wording) return first
  return (
    matches
      .slice(1, 4)
      .find(
        (candidate) =>
          first.canonical_path.startsWith(`${candidate.canonical_path}.`) &&
          candidate.authoritative_text.replace(/\s+/g, " ").includes(wording),
      ) ?? first
  )
}
