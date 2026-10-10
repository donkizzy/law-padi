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

export function useProvision(path: string, release?: string) {
  return useQuery({
    queryKey: ["legal", "provision", path, release],
    queryFn: async ({ signal }) =>
      (
        await LegalService.readCurrentProvision({
          path: { canonical_path: path },
          query: { release_version: release },
          signal,
        })
      ).data.data[0],
    enabled: Boolean(path),
    retry: false,
  })
}

export function useProvisionTree(parent?: string, release?: string) {
  return useQuery({
    queryKey: ["legal", "tree", parent, release],
    queryFn: async ({ signal }) =>
      (
        await LegalService.readProvisionTree({
          query: { parent_path: parent, release_version: release },
          signal,
        })
      ).data,
    retry: false,
  })
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
    if (error.response?.status === 404)
      return "This provision or published edition was not found."
    if (error.response?.status === 503)
      return "The published corpus is temporarily unavailable. Please try again."
  }
  return "We could not load the source. Check your connection and try again."
}
