#!/usr/bin/env node
// Copies the live analyzer artifacts into web/snapshot/ so a commit + push
// deploys a frozen snapshot (Vercel reads web/snapshot/ since the local work/
// dir is absent there). Source resolution mirrors lib/data.ts:
//   HJ_DATA_ROOT  ->  HJ_WORK_DIR  ->  ../config.json work dir
import fs from "node:fs";
import path from "node:path";

const cwd = process.cwd(); // web/
const repoRoot = path.join(cwd, "..");

function resolveWorkDir() {
  if (process.env.HJ_DATA_ROOT) return path.join(process.env.HJ_DATA_ROOT, "work");
  if (process.env.HJ_WORK_DIR) return process.env.HJ_WORK_DIR;
  let workRel = "work";
  try {
    const cfg = JSON.parse(fs.readFileSync(path.join(repoRoot, "config.json"), "utf8"));
    workRel = cfg?.paths?.work_dir ?? workRel;
  } catch {
    // no ../config.json — fall back to default
  }
  return path.resolve(repoRoot, workRel);
}

function dirSize(dir) {
  if (!fs.existsSync(dir)) return 0;
  return fs.readdirSync(dir).reduce((sum, name) => {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    return sum + (st.isDirectory() ? dirSize(p) : st.size);
  }, 0);
}

const workDir = resolveWorkDir();
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

// submissions.json carries team members incl. their emails (PII). The snapshot
// is the committed/deployable artifact, so strip emails by default — the live
// local dashboard (reading work/ directly) still shows them for admin use. Set
// HJ_SNAPSHOT_KEEP_EMAILS=1 for a private deploy that intentionally needs them.
const keepEmails = process.env.HJ_SNAPSHOT_KEEP_EMAILS === "1";
const submissions = path.join(workDir, "submissions.json");
const snapshotSubs = path.join(snapshot, "submissions.json");
let redactedCount = 0;
if (fs.existsSync(submissions)) {
  if (keepEmails) {
    fs.copyFileSync(submissions, snapshotSubs);
  } else {
    const records = JSON.parse(fs.readFileSync(submissions, "utf8"));
    for (const rec of records) {
      for (const member of rec?.members ?? []) {
        if (member && member.email) {
          member.email = "";
          redactedCount += 1;
        }
      }
    }
    fs.writeFileSync(snapshotSubs, JSON.stringify(records, null, 2) + "\n");
  }
} else {
  fs.writeFileSync(snapshotSubs, "[]\n");
}

const rowCount = fs.readFileSync(summaryCsv, "utf8").trim().split("\n").length - 1;
console.log("✓ Snapshot written to web/snapshot/");
console.log(`  source: ${workDir}`);
console.log(`  repos:  ${rowCount}`);
console.log(`  size:   ${(dirSize(snapshot) / 1024).toFixed(1)} KB`);
console.log(
  keepEmails
    ? "  emails: KEPT (HJ_SNAPSHOT_KEEP_EMAILS=1) — snapshot contains PII"
    : `  emails: redacted ${redactedCount} member email(s) from submissions.json`,
);
console.log("\nCommit web/snapshot/ and push to deploy the frozen snapshot.");
