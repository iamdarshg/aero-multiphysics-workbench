// One-command solver setup for average users. Safe by design:
// - installs micromamba (static binary) only if missing, into the user profile
// - creates/updates the conda env from infra/local/solver-environment.yml
// - never touches system dirs, never needs sudo, never starts servers
// - prints a capability report; anything unavailable stays fail-closed
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { homedir, platform } from "node:os";
import { join } from "node:path";

const root = join(import.meta.dirname, "..", "..");
const envFile = join(root, "infra", "local", "solver-environment.yml");
const binDir = join(homedir(), ".local", "bin");
const micro = join(binDir, platform() === "win32" ? "micromamba.exe" : "micromamba");
const envDir = join(homedir(), ".local", "share", "aero-solvers");

const run = (cmd, args, opts = {}) => {
  const r = spawnSync(cmd, args, { encoding: "utf8", shell: false, ...opts });
  return r;
};

if (!existsSync(micro)) {
  console.log("Installing micromamba (static binary, user profile only)...");
  mkdirSync(binDir, { recursive: true });
  const url =
    platform() === "win32"
      ? "https://micro.mamba.pm/api/micromamba/win-64/latest"
      : platform() === "darwin"
        ? "https://micro.mamba.pm/api/micromamba/osx-64/latest"
        : "https://micro.mamba.pm/api/micromamba/linux-64/latest";
  const dl =
    platform() === "win32"
      ? run("powershell", ["-NoProfile", "-Command", `Invoke-WebRequest -Uri ${url} -OutFile ${join(binDir, "micro.tar.bz2")}`])
      : run("curl", ["-sL", url, "-o", join(binDir, "micro.tar.bz2")]);
  if (dl.status !== 0) throw new Error("micromamba download failed; check network and retry");
  const untar =
    platform() === "win32"
      ? run("tar", ["-xjf", join(binDir, "micro.tar.bz2"), "-C", binDir])
      : run("tar", ["-xj", "-C", binDir, "-f", join(binDir, "micro.tar.bz2")]);
  if (untar.status !== 0 || !existsSync(micro)) throw new Error("micromamba unpack failed");
  console.log("micromamba ready.");
}

console.log("Creating solver environment (conda-forge; several minutes, one time)...");
const create = run(micro, ["create", "-y", "-p", envDir, "-f", envFile], { stdio: "inherit" });
if (create.status !== 0) throw new Error("solver env creation failed; rerun to resume");
console.log(`\nSolvers installed at ${envDir}. Activate per-shell; no servers started.`);
console.log("Verifying...");
const py = platform() === "win32" ? join(envDir, "python.exe") : join(envDir, "bin", "python");
const check = run(py, ["-c", "import importlib.util as u; print([(m, u.find_spec(m) is not None) for m in ['openmdao','ross','pybamm','cantera','gmsh']])"]);
console.log(check.stdout.trim() || "(python check skipped)");
console.log("Done. Anything still missing is reported unavailable by capabilities.mjs (fail-closed).");
