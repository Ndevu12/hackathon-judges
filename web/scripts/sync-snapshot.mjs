#!/usr/bin/env node
// Copies the live analyzer artifacts into web/snapshot/ so a commit + push
// deploys a frozen snapshot (Vercel reads web/snapshot/ since the local work/
// dir is absent there). Source resolution mirrors lib/data.ts:
//   HJ_DATA_ROOT  ->  HJ_WORK_DIR (+HJ_JUDGE_JSON)  ->  ../config.json
import fs from "node:fs";
import path from "node:path";

const cwd = process.cwd(); // web/
const repoRoot = path.join(cwd, "..");

function resolveSource() {
  const root = process.env.HJ_DATA_ROOT;
  if (root) {
    return {
      workDir: path.join(root, "work"),
      judgeJson: path.join(root, "data", "judge-responses-normalized.json"),
    };
  }
  if (process.env.HJ_WORK_DIR) {
    return {
      workDir: process.env.HJ_WORK_DIR,
      judgeJson: process.env.HJ_JUDGE_JSON ?? "",
    };
  }
  let workRel = "work";
  let judgeRel = "data/judge-responses-normalized.json";
  try {
    const cfg = JSON.parse(fs.readFileSync(path.join(repoRoot, "config.json"), "utf8"));
    workRel = cfg?.paths?.work_dir ?? workRel;
    judgeRel = cfg?.paths?.judge_responses_normalized ?? judgeRel;
  } catch {
    // no ../config.json — fall back to defaults
  }
  return {
    workDir: path.resolve(repoRoot, workRel),
    judgeJson: path.resolve(repoRoot, judgeRel),
  };
}

function dirSize(dir) {
  if (!fs.existsSync(dir)) return 0;
  return fs.readdirSync(dir).reduce((sum, name) => {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    return sum + (st.isDirectory() ? dirSize(p) : st.size);
  }, 0);
}

const { workDir, judgeJson } = resolveSource();
const summaryCsv = path.join(workDir, "summary", "metrics_summary.csv");

if (!fs.existsSync(summaryCsv)) {
  console.error(`✗ No metrics_summary.csv at ${summaryCsv}`);
  console.error("  Run scan.py first, or set HJ_DATA_ROOT / HJ_WORK_DIR.");
  process.exit(1);
}

const snapshot = path.join(cwd, "snapshot");
fs.rmSync(snapshot, { recursive: true, force: true });
fs.mkdirSync(path.join(snapshot, "summary"), { recursive: true });

fs.copyFileSync(summaryCsv, path.join(snapshot, "summary", "metrics_summary.csv"));

const metricsDir = path.join(workDir, "metrics");
if (fs.existsSync(metricsDir)) {
  fs.cpSync(metricsDir, path.join(snapshot, "metrics"), { recursive: true });
}

const aiDir = path.join(workDir, "ai_outputs");
if (fs.existsSync(aiDir)) {
  fs.cpSync(aiDir, path.join(snapshot, "ai_outputs"), { recursive: true });
}

const snapshotJudge = path.join(snapshot, "judge-responses-normalized.json");
if (judgeJson && fs.existsSync(judgeJson)) {
  fs.copyFileSync(judgeJson, snapshotJudge);
} else {
  fs.writeFileSync(
    snapshotJudge,
    JSON.stringify({ by_repo: {}, unmapped_responses: [] }, null, 2),
  );
}

const rowCount = fs.readFileSync(summaryCsv, "utf8").trim().split("\n").length - 1;
console.log("✓ Snapshot written to web/snapshot/");
console.log(`  source: ${workDir}`);
console.log(`  repos:  ${rowCount}`);
console.log(`  size:   ${(dirSize(snapshot) / 1024).toFixed(1)} KB`);
console.log("\nCommit web/snapshot/ and push to deploy the frozen snapshot.");
