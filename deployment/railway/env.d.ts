// railway.ts reads the repository name from the environment of the
// `railway config` run; this avoids a dependency on Node's type definitions.
declare const process: { env: Record<string, string | undefined> };
