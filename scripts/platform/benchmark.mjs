import { spawnSync } from "node:child_process";

const result = spawnSync(process.execPath, ["--test", "tests/platform/platform.test.ts"], { stdio: "inherit", shell: false });
process.exit(result.status ?? 1);
