// Runtime entrypoint for the lightweight platform image (Docker only).
//
// Single-service modes so compose can order api/web/mcp independently:
//   api  -> uvicorn serving services/api (governed job lifecycle in-process)
//   web  -> Next.js production server (needs apps/web built at image time)
//   mcp  -> stdio engineering MCP server (needs AERO_API_BASE_URL)
//
// The child runs with inherited stdio; SIGTERM/SIGINT are forwarded and the
// child's exit code propagates. No solvers are launched here.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MODES = Object.freeze(["api", "web", "mcp"]);

/**
 * Resolve the venv site-packages for the API's PYTHONPATH.
 *
 * The API is launched with the image's own `python3` and the venv's
 * site-packages on PYTHONPATH, so a venv interpreter symlink that is broken in
 * the shipped image can never make the container fail with ENOENT.
 */
export const resolveSitePackages = (env = {}) => {
  const venv = env.VIRTUAL_ENV?.trim();
  if (!venv) return null;
  for (const version of ["python3.12", "python3"]) {
    const candidate = join(venv, "lib", version, "site-packages");
    if (existsSync(candidate)) return candidate;
  }
  return null;
};

/**
 * Resolve the API interpreter to an absolute image path.
 *
 * A bare `python3` can resolve to a dangling venv symlink that shadows PATH and
 * fails with ENOENT; address the image interpreter directly instead.
 */
export const resolveInterpreter = () => {
  for (const candidate of ["/usr/local/bin/python3", "/usr/bin/python3"]) {
    if (existsSync(candidate)) return candidate;
  }
  return "python3";
};

const usageError = (detail) => new Error(`ENTRYPOINT_USAGE:${detail}`);

export const parseMode = (argv) => {
  if (argv.includes("--help") || argv.includes("-h")) return { mode: null, help: true };
  const [mode, ...rest] = argv;
  if (!mode || rest.length > 0 || !MODES.includes(mode)) {
    throw usageError(`expected exactly one of: ${MODES.join(" | ")}`);
  }
  return { mode, help: false };
};

export const resolveServiceCommand = ({ mode, root, env = {} }) => {
  if (mode === "api") {
    const port = env.AERO_API_PORT?.trim() ? Number(env.AERO_API_PORT) : 8000;
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw usageError(`invalid AERO_API_PORT=${JSON.stringify(env.AERO_API_PORT)}`);
    }
    const jobRoot = env.AEROWORKBENCH_JOB_ROOT?.trim() || "/data/jobs";
    mkdirSync(jobRoot, { recursive: true });
    const sitePackages = resolveSitePackages(env);
    const pythonPath = [sitePackages, env.PYTHONPATH]
      .filter((value) => typeof value === "string" && value.trim() !== "")
      .join(":");
    return {
      cmd: resolveInterpreter(),
      argv: ["-m", "uvicorn", "aeroworkbench_api.main:app", "--host", "0.0.0.0", "--port", String(port)],
      cwd: join(root, "services", "api"),
      extraEnv: {
        AEROWORKBENCH_JOB_ROOT: jobRoot,
        ...(pythonPath ? { PYTHONPATH: pythonPath } : {}),
      },
    };
  }
  if (mode === "web") {
    const port = env.AERO_WEB_PORT?.trim() ? Number(env.AERO_WEB_PORT) : 3000;
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw usageError(`invalid AERO_WEB_PORT=${JSON.stringify(env.AERO_WEB_PORT)}`);
    }
    return {
      cmd: process.execPath,
      argv: [join(root, "apps", "web", "node_modules", "next", "dist", "bin", "next"),
        "start", "--port", String(port), "--hostname", "0.0.0.0"],
      cwd: join(root, "apps", "web"),
      extraEnv: {},
    };
  }
  const apiBase = env.AERO_API_BASE_URL?.trim();
  if (!apiBase) throw usageError("mcp mode requires AERO_API_BASE_URL");
  return {
    cmd: process.execPath,
    argv: [join(root, "mcp", "engineering", "server.ts")],
    cwd: root,
    extraEnv: {},
  };
};

const printUsage = () => {
  console.log(`Usage: node infra/docker/platform-entrypoint.mjs <${MODES.join("|")}>`);
  console.log("Single-service entrypoint for the platform image (api:8000, web:3000, mcp:stdio).");
};

const main = async () => {
  const root = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
  let parsed;
  try {
    parsed = parseMode(process.argv.slice(2));
  } catch (error) {
    console.error(`[platform-entrypoint] ${error.message}`);
    printUsage();
    process.exitCode = 2;
    return;
  }
  if (parsed.help || !parsed.mode) {
    printUsage();
    return;
  }
  let service;
  try {
    service = resolveServiceCommand({ mode: parsed.mode, root, env: process.env });
  } catch (error) {
    console.error(`[platform-entrypoint] ${error.message}`);
    process.exitCode = 2;
    return;
  }
  const child = spawn(service.cmd, service.argv, {
    cwd: service.cwd,
    env: { ...process.env, ...service.extraEnv },
    shell: false,
    stdio: "inherit",
  });
  const forward = (signal) => {
    try {
      child.kill(signal);
    } catch {
      // Child already exited; the exit handler below settles the code.
    }
  };
  process.once("SIGTERM", () => forward("SIGTERM"));
  process.once("SIGINT", () => forward("SIGINT"));
  child.once("error", (error) => {
    console.error(`[platform-entrypoint] ${parsed.mode} failed to start: ${error.message}`);
    process.exitCode = 1;
  });
  child.once("exit", (code, signal) => {
    process.exitCode = code ?? (signal ? 143 : 1);
    process.exit(process.exitCode);
  });
};

const invokedDirectly = (() => {
  try {
    return resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url);
  } catch { return false; }
})();

if (invokedDirectly) await main();
