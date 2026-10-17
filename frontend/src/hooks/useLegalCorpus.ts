import { useQuery } from "@tanstack/react-query"
import { AxiosError } from "axios"
import { LegalService } from "@/client"

export function useLegalRelease() {
  return useQuery({
    queryKey: ["legal", "release"],
    queryFn: async ({ signal }) =>
      (await LegalService.readCurrentRelease({ signal })).data,
    retry: false,
    staleTime: 30_000,
  })
}

export function useLegalSearch(
  query: string,
  mode: "auto" | "semantic" = "auto",
  attempt = 0,
  releaseVersion?: string,
) {
  return useQuery({
    queryKey: ["legal", "search", query, mode, attempt, releaseVersion],
    queryFn: async ({ signal }) =>
      (
        await LegalService.searchLegal({
          body: {
            query,
            mode,
            top_k: 10,
            index_kind: "enacted",
            release_version: releaseVersion,
          },
          signal,
        })
      ).data,
    enabled: Boolean(query),
    retry: false,
  })
}

export function provisionQueryOptions(path: string, release?: string) {
  return {
    queryKey: ["legal", "provision", path, release],
    queryFn: async ({ signal }: { signal: AbortSignal }) =>
      (
        await LegalService.readCurrentProvision({
          path: { canonical_path: path },
          query: { release_version: release },
          signal,
        })
      ).data.data[0],
    staleTime: 30_000,
    retry: false as const,
  }
}

export function useProvision(path: string, release?: string) {
  return useQuery({
    ...provisionQueryOptions(path, release),
    enabled: Boolean(path),
  })
}

export function treeQueryOptions(parent?: string, release?: string) {
  return {
    queryKey: ["legal", "tree", parent, release],
    queryFn: async ({ signal }: { signal: AbortSignal }) =>
      (
        await LegalService.readProvisionTree({
          query: { parent_path: parent, release_version: release },
          signal,
        })
      ).data,
    staleTime: 30_000,
    retry: false as const,
  }
}

export function useProvisionTree(parent?: string, release?: string) {
  return useQuery(treeQueryOptions(parent, release))
}

export function useProvisionHistory(
  path: string,
  release: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["legal", "history", path, release],
    queryFn: async ({ signal }) =>
      (
        await LegalService.readProvisionHistory({
          query: { canonical_path: path, release_version: release },
          signal,
        })
      ).data,
    enabled,
    retry: false,
  })
}

export function legalError(error: unknown): string {
  if (error instanceof AxiosError) {
    if (error.response?.status === 404) return "We couldn't find that section."
    if (error.response?.status === 503)
      return "The Constitution can't be loaded right now. Please try again in a moment."
  }
  return "Something went wrong loading this. Check your connection and try again."
}
