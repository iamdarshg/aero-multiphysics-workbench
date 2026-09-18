// Container smoke: build the lightweight platform image, start the compose
// stack, verify a healthy API + UI plus one terminal native_solver product
// job, then shut down cleanly. Fails closed everywhere (missing daemon,
// failed build, unhealthy API, non-terminal job); never fakes success.
//
// The job verification reuses runProductJob from product-smoke.mjs so the
// container path checks exactly what the local smoke checks.
//
// Usage: node scripts/platform/container-smoke.mjs [--image TAG]
//   [--api-port N] [--web-port N]
import { spawn } from "node:child_process";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { SMOKE_INPUTS, SMOKE_PARTICIPANT, runProductJob, waitForHealth } from "./product-smoke.mjs";

export const CONTAINER_SMOKE_SCHEMA = 1;
export const BUILD_TIMEOUT_MS_DEFAULT = 1_200_000;
export const HEALTH_TIMEOUT_MS_DEFAULT = 300_000;
export const JOB_TIMEOUT_MS_DEFAULT = 600_000;
export const CMD_TIMEOUT_MS_DEFAULT = 120_000;

const smokeError = (code, detail) => new Error(`${code}:${detail}`);

export const parseArgs = (argv) => {
  const parsed = {
    image: "aero-platform:ci",
    apiPort: 8000,
    webPort: 3000,
    buildTimeoutMs: BUILD_TIMEOUT_MS_DEFAULT,
    healthTimeoutMs: HEALTH_TIMEOUT_MS_DEFAULT,
    jobTimeoutMs: JOB_TIMEOUT_MS_DEFAULT,
    help: false,
  };
  const args = [...argv];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") return { ...parsed, help: true };
    if (arg === "--image" || arg === "--api-port" || arg === "--web-port") {
      const raw = args[index + 1];
      if (raw === undefined) throw smokeError("SMOKE_USAGE", `missing value for ${arg}`);
      index += 1;
      if (arg === "--image") {
        if (!/^[a-z0-9][a-z0-9._/-]*(:[a-z0-9._-]+)?$/i.test(raw)) {
          throw smokeError("SMOKE_USAGE", `invalid --image ${JSON.stringify(raw)}`);
        }
        parsed.image = raw;
      } else {
        const value = Number(raw);
        if (!Number.isInteger(value) || value < 1 || value > 65535) {
          throw smokeError("SMOKE_USAGE", `invalid ${arg}=${JSON.stringify(raw)}`);
        }
        if (arg === "--api-port") parsed.apiPort = value;
        else parsed.webPort = value;
      }
    } else {
      throw smokeError("SMOKE_USAGE", `unknown argument: ${arg}`);
    }
  }
  return parsed;
};

export const resolveConfig = ({ argv, env = {}, root }) => {
  const parsed = parseArgs(argv);
  return {
    schema: CONTAINER_SMOKE_SCHEMA,
    help: parsed.help,
    image: env.AERO_PLATFORM_IMAGE?.trim() || parsed.image,
    apiPort: parsed.apiPort,
    webPort: parsed.webPort,
    buildTimeoutMs: parsed.buildTimeoutMs,
    healthTimeoutMs: parsed.healthTimeoutMs,
    jobTimeoutMs: parsed.jobTimeoutMs,
    pollMs: 2_000,
    root,
    dockerfile: join(root, "infra", "docker", "Dockerfile.platform"),
    composeFile: join(root, "infra", "docker", "compose.local.yml"),
    apiBase: `http://127.0.0.1:${parsed.apiPort}`,
    webBase: `http://127.0.0.1:${parsed.webPort}`,
  };
};

const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));

const runCmd = (cmd, args, { cwd, timeoutMs }) => new Promise((resolveCmd, rejectCmd) => {
  const child = spawn(cmd, args, { cwd, shell: false, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  let output = "";
  const collect = (chunk) => {
    output += String(chunk);
    if (output.length > 20_000) output = output.slice(-20_000);
  };
  child.stdout?.on("data", collect);
  child.stderr?.on("data", collect);
  const timer = setTimeout(() => {
    child.kill("SIGKILL");
    rejectCmd(smokeError("SMOKE_CMD_TIMEOUT", `${cmd} ${args.join(" ")} exceeded ${timeoutMs}ms`));
  }, timeoutMs);
  child.once("error", (error) => {
    clearTimeout(timer);
    rejectCmd(smokeError("SMOKE_CMD_FAILED", `${cmd} could not start: ${error.message}`));
  });
  child.once("exit", (code) => {
    clearTimeout(timer);
    if (code === 0) resolveCmd(output);
    else {
      rejectCmd(smokeError("SMOKE_CMD_FAILED",
        `${cmd} ${args.join(" ")} exited ${code}; tail: ${output.slice(-800)}`));
    }
  });
});

const compose = (config, ...args) => runCmd("docker",
  ["compose", "-f", config.composeFile, ...args],
  { cwd: config.root, timeoutMs: CMD_TIMEOUT_MS_DEFAULT });

const printUsage = () => {
  console.log("Usage: node scripts/platform/container-smoke.mjs [--image TAG] [--api-port N] [--web-port N]");
  console.log("");
  console.log("Builds the platform image, starts api+web via compose.local.yml, waits");
  console.log("for health, runs one rotor-campbell product job to a verified");
  console.log("native_solver envelope, then composes down. Requires a Docker daemon.");
};

const main = async () => {
  const root = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
  let config;
  try {
    config = resolveConfig({ argv: process.argv.slice(2), env: process.env, root });
  } catch (error) {
    console.error(`[container-smoke] ${error.message}`);
    printUsage();
    process.exitCode = 2;
    return;
  }
  if (config.help) {
    printUsage();
    return;
  }
  let started = false;
  try {
    await runCmd("docker", ["info"], { cwd: root, timeoutMs: 15_000 }).catch((error) => {
      throw smokeError("SMOKE_NO_DAEMON", `no Docker daemon answered docker info: ${error.message}`);
    });
    console.log(`[container-smoke] building ${config.image}`);
    await runCmd("docker",
      ["build", "-f", config.dockerfile, "-t", config.image, "."],
      { cwd: root, timeoutMs: config.buildTimeoutMs });
    console.log("[container-smoke] starting api+web");
    await compose(config, "up", "-d", "--build", "api", "web");
    started = true;
    await waitForHealth({
      url: `${config.apiBase}/health`,
      deadlineMs: Date.now() + config.healthTimeoutMs,
      pollMs: config.pollMs,
    });
    console.log("[container-smoke] API healthy; checking web");
    await waitForHealth({
      url: config.webBase,
      deadlineMs: Date.now() + config.healthTimeoutMs,
      pollMs: config.pollMs,
    });
    console.log("[container-smoke] web healthy; running product job");
    const summary = await runProductJob(config.apiBase, {
      participantId: SMOKE_PARTICIPANT,
      inputs: { ...SMOKE_INPUTS },
      jobTimeoutMs: config.jobTimeoutMs,
      pollMs: config.pollMs,
    });
    console.log(JSON.stringify({
      tool: "aero-container-smoke",
      schema: CONTAINER_SMOKE_SCHEMA,
      image: config.image,
      apiBase: config.apiBase,
      webBase: config.webBase,
      ...summary,
    }, null, 2));
  } catch (error) {
    console.error(`[container-smoke] ${error.message}`);
    // Diagnostics: surface the service logs so a failed container start or a
    // crashed Next.js server is actionable without reproducing locally.
    for (const service of ["api", "web"]) {
      try {
        const logs = await compose(config, "logs", "--no-color", "--tail", "120", service);
        console.error(`[container-smoke] ${service} logs:\n${logs.slice(-8000)}`);
      } catch {
        // best effort only; the exit code below is authoritative
      }
    }
    process.exitCode = 1;
  } finally {
    if (started) {
      try {
        await compose(config, "down");
        console.log("[container-smoke] stack stopped cleanly");
      } catch (error) {
        console.error(`[container-smoke] compose down failed: ${error.message}`);
        if (process.exitCode === 0) process.exitCode = 1;
      }
    }
    await sleep(0);
  }
};

const invokedDirectly = (() => {
  try {
    return resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url);
  } catch { return false; }
})();

if (invokedDirectly) await main();
