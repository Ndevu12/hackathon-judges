import "server-only";
import fs from "node:fs";
import path from "node:path";

// Reads the analyzer's config.json from the repo root (one level above web/) to
// locate the live work dir during local `npm run dev`. Returns null when
// unavailable (e.g. on Vercel where the root directory is web/).
export interface RepoConfig {
  workDir: string;
}

export function readRepoConfig(): RepoConfig | null {
  const repoRoot = path.join(process.cwd(), "..");
  const configPath = path.join(repoRoot, "config.json");
  if (!fs.existsSync(configPath)) return null;
  const cfg = JSON.parse(fs.readFileSync(configPath, "utf8"));
  const paths = cfg?.paths ?? {};
  return { workDir: path.resolve(repoRoot, paths.work_dir ?? "work") };
}
