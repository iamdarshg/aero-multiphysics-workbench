import assert from "node:assert/strict";
import { resolve } from "node:path";
import test from "node:test";

import {
  DEFAULTS,
  EXIT,
  STARTUP_ORDER,
  resolveApiPythonPath,
  resolveConfig,
  startStack,
  stopStack,
} from "../../scripts/platform/stack.mjs";

const SOLVER_EXECUTABLES = [
  "simpleFoam",
  "openfoam",
  "code-aster",
  "precice",
  "elmer",
  "cantera",
  "pycycle",
  "freecad",
  "openvsp",
  "gmsh",
];

const root = "/repo";

const baseEnv = () => ({
  AERO_API_PORT: "8000",
  AERO_WEB_PORT: "3000",
});

const baseConfig = (overrides = {}) => resolveConfig({
  argv: ["dev"],
  env: {
    ...baseEnv(),
    AERO_STACK_API_COMMAND: JSON.stringify(["stub-api"]),
    AERO_STACK_WEB_COMMAND: JSON.stringify(["stub-web"]),
    ...overrides,
  },
  root,
  nextBin: "/repo/next-bin",
});

/** Deterministic fake clock: sleep advances time, probes script readiness. */
const makeClock = () => {
  let now = 0;
  return {
    now: () => now,
    sleep: async (ms) => { now += ms; },
  };
};

const makeChild = (name, pid) => {
  const kills = [];
  const lines = [];
  const child = {
    name,
    pid,
    kills,
    exited: false,
    exitCode: null,
    stdin: [],
    lineHandlers: new Set(),
    kill: (signal) => { kills.push(signal ?? "SIGTERM"); return true; },
    isExited: () => child.exited,
    exitCodeValue: () => child.exitCode,
    lastLines: () => [...lines],
    pushLine: (line) => { lines.push(line); for (const cb of child.lineHandlers) cb(line); },
    sendStdin: (data) => { child.stdin.push(data); },
    onStdoutLine: (cb) => { child.lineHandlers.add(cb); return () => child.lineHandlers.delete(cb); },
    die: (code) => { child.exited = true; child.exitCode = code; },
  };
  return child;
};

const makeDeps = (options = {}) => {
  const clock = makeClock();
  const children = [];
  let nextPid = 1000;
  const preSpawnTcp = (() => {
    // Pre-spawn checks see free ports; once services are starting, each
    // port is held by its service (mirrors a real loopback listener).
    let calls = 0;
    return async () => {
      calls += 1;
      return calls > 2
        ? { occupied: true, detail: "a listener accepted a loopback connection" }
        : { occupied: false, detail: "port is free" };
    };
  })();
  const deps = {
    logs: [],
    spawns: [],
    forceKills: [],
    treeSnapshots: options.treeSnapshots ?? {},
    httpCalls: [],
    httpBehavior: options.httpBehavior ?? (async () => ({ status: 200 })),
    tcpBehavior: options.tcpBehavior ?? preSpawnTcp,
    now: clock.now,
    sleep: clock.sleep,
    log: (line) => { deps.logs.push(line); },
    fsAccess: async () => {},
    readTreePids: async (pid) => deps.treeSnapshots[pid] ?? [pid],
    forceKill: async (rootPid, pids) => {
      deps.forceKills.push({ rootPid, pids: [...pids] });
      for (const child of children) {
        if (pids.includes(child.pid)) child.die(null);
      }
    },
    httpGet: async (url) => { deps.httpCalls.push(url); return deps.httpBehavior(url); },
    tcpProbe: async (host, port) => deps.tcpBehavior(host, port),
    spawnService: (name, cmd, spawnOptions) => {
      deps.spawns.push({ name, cmd, spawnOptions });
      const child = makeChild(name, nextPid++);
      children.push(child);
      if (options.onSpawn) options.onSpawn(child);
      return child;
    },
    children,
  };
  return deps;
};

test("mocked children become ready => parent reports ready with real URLs", async () => {
  const config = baseConfig();
  const deps = makeDeps();
  const handle = await startStack(config, deps);
  assert.deepEqual(handle.services.map((service) => service.name), ["api", "web"]);
  assert.ok(deps.logs.some((line) => line.includes("stack ready")));
  assert.ok(deps.logs.some((line) => line.includes("http://127.0.0.1:8000")));
  assert.ok(deps.logs.some((line) => line.includes("http://127.0.0.1:3000")));
  assert.ok(deps.httpCalls.some((url) => url.endsWith("/health")));
  assert.ok(deps.httpCalls.some((url) => url.endsWith("/v1/native/capabilities")));
  await stopStack(handle, deps);
});

test("MCP omitted => only api and web spawn and the stack still works", async () => {
  const config = baseConfig();
  const deps = makeDeps();
  const handle = await startStack(config, deps);
  assert.deepEqual(deps.spawns.map((spawn) => spawn.name), ["api", "web"]);
  assert.equal(handle.services.length, 2);
  await stopStack(handle, deps);
});

test("--with-mcp spawns the stdio MCP server after a successful handshake", async () => {
  const config = baseConfig();
  config.withMcp = true;
  const deps = makeDeps({
    onSpawn: (child) => {
      if (child.name === "mcp") {
        queueMicrotask(() => {
          assert.match(child.stdin.join(""), /"method":"initialize"/);
          child.pushLine(JSON.stringify({ jsonrpc: "2.0", id: "stack-probe", result: { protocolVersion: "2025-06-18", serverInfo: { name: "aero-engineering" } } }));
        });
      }
    },
  });
  const handle = await startStack(config, deps);
  assert.deepEqual(handle.services.map((service) => service.name), ["api", "web", "mcp"]);
  await stopStack(handle, deps);
});

test("one child fails startup => previously started children terminate", async () => {
  const config = baseConfig();
  const deps = makeDeps({
    onSpawn: (child) => {
      if (child.name === "web") child.die(1);
    },
  });
  await assert.rejects(startStack(config, deps), /STACK_STARTUP_FAILED:web/);
  const api = deps.children.find((child) => child.name === "api");
  assert.ok(api.kills.length > 0);
  assert.ok(deps.forceKills.some((kill) => kill.pids.includes(api.pid)));
});

test("timeout => clean failure naming the component with no survivors", async () => {
  const config = baseConfig({ AERO_STACK_READY_TIMEOUT_MS: "1000" });
  const deps = makeDeps({ httpBehavior: async () => { throw new Error("connection refused"); } });
  await assert.rejects(startStack(config, deps), /STACK_START_TIMEOUT:api/);
  const api = deps.children.find((child) => child.name === "api");
  assert.ok(deps.forceKills.some((kill) => kill.pids.includes(api.pid)));
  assert.deepEqual(deps.spawns.map((spawn) => spawn.name), ["api"]);
});

test("port conflict => actionable error before anything spawns", async () => {
  const config = baseConfig();
  const deps = makeDeps({
    tcpBehavior: async (host, port) => (
      port === 3000
        ? { occupied: true, detail: "a listener accepted a loopback connection" }
        : { occupied: false, detail: "port is free" }
    ),
  });
  await assert.rejects(startStack(config, deps), /port 3000 \(web UI\) is occupied/);
  await assert.rejects(startStack(config, deps), /AERO_WEB_PORT/);
  assert.equal(deps.spawns.length, 0);
});

test("stopStack terminates in reverse dependency order with bounded force", async () => {
  const config = baseConfig();
  config.withMcp = true;
  const order = [];
  const deps = makeDeps({
    treeSnapshots: {},
    onSpawn: (child) => {
      if (child.name === "mcp") {
        queueMicrotask(() => {
          child.pushLine(JSON.stringify({ jsonrpc: "2.0", id: "stack-probe", result: {} }));
        });
      }
      const originalKill = child.kill;
      child.kill = (signal) => {
        order.push(child.name);
        if (child.name === "web") return originalKill(signal); // web stays alive => force path
        child.die(0);
        return originalKill(signal);
      };
    },
  });
  const handle = await startStack(config, deps);
  await stopStack(handle, deps);
  assert.deepEqual(order, ["mcp", "web", "api"]);
  const web = deps.children.find((child) => child.name === "web");
  assert.ok(deps.forceKills.some((kill) => kill.pids.includes(web.pid)));
  // Force kill only touches observed project-owned pids, never the whole host.
  for (const kill of deps.forceKills) {
    assert.ok(kill.pids.length >= 1);
    assert.ok(kill.pids.every((pid) => Number.isInteger(pid) && pid > 0));
  }
});

test("default service commands never launch heavyweight solver executables", () => {
  for (const mode of ["dev", "start"]) {
    const config = resolveConfig({ argv: [mode], env: baseEnv(), root, nextBin: "/repo/next-bin" });
    const commands = [config.apiCommand, config.webCommand, config.mcpCommand];
    for (const command of commands) {
      const text = command.join(" ").toLowerCase();
      for (const executable of SOLVER_EXECUTABLES) {
        assert.ok(!text.includes(executable), `${mode}: ${command.join(" ")} mentions ${executable}`);
      }
    }
  }
  const dev = resolveConfig({ argv: ["dev"], env: baseEnv(), root, nextBin: "/repo/next-bin" });
  assert.ok(dev.apiCommand.includes("--reload"));
  const start = resolveConfig({ argv: ["start"], env: baseEnv(), root, nextBin: "/repo/next-bin" });
  assert.ok(!start.apiCommand.includes("--reload"));
});

test("invalid ports and modes fail closed with usage errors", () => {
  assert.throws(() => resolveConfig({ argv: ["dev"], env: { ...baseEnv(), AERO_API_PORT: "abc" }, root, nextBin: "nb" }), /STACK_USAGE/);
  assert.throws(() => resolveConfig({ argv: ["dev"], env: { ...baseEnv(), AERO_WEB_PORT: "99999" }, root, nextBin: "nb" }), /STACK_USAGE/);
  assert.throws(() => resolveConfig({ argv: ["bogus"], env: baseEnv(), root, nextBin: "nb" }), /STACK_USAGE/);
  assert.throws(() => resolveConfig({ argv: ["dev", "--docker"], env: baseEnv(), root, nextBin: "nb" }), /compose\.local\.yml/);
});

test("env overrides keep the UI/API contract predictable, never random", () => {
  const config = resolveConfig({
    argv: ["dev"],
    env: { AERO_API_PORT: "18080", AERO_WEB_PORT: "13000" },
    root,
    nextBin: "nb",
  });
  assert.equal(config.apiPort, 18080);
  assert.equal(config.webPort, 13000);
  assert.ok(config.apiCommand.includes("18080"));
  assert.ok(config.webCommand.includes("13000"));
  assert.equal(DEFAULTS.apiPort, 8000);
  assert.equal(DEFAULTS.webPort, 3000);
});

test("the API import path is rebuilt from the repo's own pytest config", async () => {
  const readText = async () => 'pythonpath = ["../../packages/core", "."]\n';
  const joined = await resolveApiPythonPath({ root: "/repo", pathDelimiter: ":", readText });
  assert.equal(joined, `${resolve("/repo/services/api", "../../packages/core")}:${resolve("/repo/services/api", ".")}`);
  assert.equal(await resolveApiPythonPath({ root: "/repo", readText: async () => { throw new Error("no pyproject"); } }), null);
  assert.equal(await resolveApiPythonPath({ root: "/repo", readText: async () => "[project]\nname = 'x'\n" }), null);
});

test("apiExtraEnv reaches the API child environment", async () => {
  const config = baseConfig();
  config.apiExtraEnv = { PYTHONPATH: "/repo/packages/core" };
  const deps = makeDeps();
  const handle = await startStack(config, deps);
  assert.deepEqual(deps.spawns.find((spawn) => spawn.name === "api").spawnOptions.extraEnv, { PYTHONPATH: "/repo/packages/core" });
  await stopStack(handle, deps);
});

test("exit codes distinguish usage, failure, and interruption", () => {
  assert.equal(EXIT.OK, 0);
  assert.equal(EXIT.FAILURE, 1);
  assert.equal(EXIT.USAGE, 2);
  assert.equal(EXIT.INTERRUPTED, 130);
  assert.deepEqual(STARTUP_ORDER, ["api", "web", "mcp"]);
});
