import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const readme = readFileSync(resolve(repoRoot, "README.md"), "utf8");
const pkg = JSON.parse(readFileSync(resolve(repoRoot, "package.json"), "utf8")) as {
  scripts: Record<string, string>;
};

// pnpm subcommands that are not workspace scripts (install, exec, config, ...).
const PNPM_SUBCOMMANDS = new Set([
  "install",
  "exec",
  "dlx",
  "run",
  "add",
  "remove",
  "config",
  "store",
  "approve-builds",
  "init",
  "create",
  "audit",
  "outdated",
  "list",
  "ls",
  "view",
  "info",
  "publish",
  "pack",
  "prune",
  "rebuild",
  "fetch",
  "deploy",
  "why",
  "ping",
  "login",
  "logout",
  "whoami",
  "link",
  "unlink",
]);

describe("README command contract (issue #9)", () => {
  it("documents the full quickstart command surface", () => {
    for (const command of [
      "pnpm setup",
      "pnpm run doctor",
      "pnpm setup:solvers",
      "pnpm dev:all",
      "pnpm start:local",
      "pnpm smoke:product",
    ]) {
      assert.ok(readme.includes(command), `README must document quickstart command: ${command}`);
    }
  });

  it("resolves every pnpm script mention against package.json", () => {
    const pattern = /pnpm\s+(?:run\s+)?([A-Za-z0-9@:][A-Za-z0-9:@/_.-]*)/g;
    const unknown = new Set<string>();
    for (let match = pattern.exec(readme); match !== null; match = pattern.exec(readme)) {
      const token = match[1];
      if (token.startsWith("-") || token.startsWith("@") || token.includes("/")) continue;
      if (PNPM_SUBCOMMANDS.has(token)) continue;
      if (!(token in pkg.scripts)) unknown.add(token);
    }
    assert.deepEqual([...unknown].sort(), [], "README references unknown pnpm scripts");
  });

  it("references only local files that exist", () => {
    const pathPattern =
      /`((?:scripts|docs|infra|tests|services|apps|packages|mcp)\/[A-Za-z0-9_.\-/]+)`/g;
    const missing = new Set<string>();
    for (let match = pathPattern.exec(readme); match !== null; match = pathPattern.exec(readme)) {
      if (!existsSync(resolve(repoRoot, match[1]))) missing.add(match[1]);
    }
    for (const name of ["LICENSE", "SECURITY.md", "CONTRIBUTING.md"]) {
      assert.ok(readme.includes(name), `README must reference ${name}`);
      assert.ok(existsSync(resolve(repoRoot, name)), `${name} must exist`);
    }
    assert.deepEqual([...missing].sort(), [], "README references missing local files");
  });
});
