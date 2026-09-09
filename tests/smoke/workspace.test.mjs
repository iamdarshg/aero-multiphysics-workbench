import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));

test("every declared workspace package has a manifest and test command", async () => {
  const workspace = await readFile(join(root, "pnpm-workspace.yaml"), "utf8");
  const patterns = [...workspace.matchAll(/^\s*-\s*["']([^"']+)["']/gm)].map((match) => match[1]);
  assert.ok(patterns.length > 0, "pnpm-workspace.yaml declares no package globs");
  const packages = [];
  for (const pattern of patterns) {
    const [folder] = pattern.split("/*");
    const packageRoot = join(root, folder);
    let entries;
    try { entries = await readdir(packageRoot, { withFileTypes: true }); } catch { continue; }
    for (const entry of entries.filter((candidate) => candidate.isDirectory())) {
      const packageJsonPath = join(packageRoot, entry.name, "package.json");
      try {
        const manifest = JSON.parse(await readFile(packageJsonPath, "utf8"));
        packages.push({ path: packageJsonPath, manifest });
      } catch {
        // A glob may be empty or contain a non-package directory.
      }
    }
  }
  assert.ok(packages.length > 0, "no workspace package manifests found");
  for (const { path, manifest } of packages) {
    assert.equal(typeof manifest.name, "string", `${path} has no package name`);
    assert.equal(typeof manifest.scripts?.test, "string", `${path} has no test script`);
  }
});
