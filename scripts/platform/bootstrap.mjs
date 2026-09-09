import { spawnSync } from "node:child_process";

const node = spawnSync(process.execPath, ["--version"], { encoding: "utf8", shell: false });
if (node.status !== 0) throw new Error("Node.js runtime check failed");
console.log(`Bootstrap safety check: Node ${node.stdout.trim()}`);
console.log("No native solver, container image, cloud resource, credential, or dependency was installed or changed.");
console.log("Running capability inspection (exit 2 means native tools are unavailable, not a bootstrap failure).");
const capabilities = spawnSync(process.execPath, ["scripts/platform/capabilities.mjs"], { stdio: "inherit", shell: false });
process.exitCode = capabilities.status === 0 || capabilities.status === 2 ? 0 : (capabilities.status ?? 1);
