// Bounded live start/stop coverage for the local stack orchestrator.
//
// These tests spawn the real `scripts/platform/stack.mjs` CLI with stub API
// and web servers (plain `node -e` loopback listeners, no solvers, no Docker)
// and verify genuine end-to-end behavior: readiness is reported only after the
// gates respond, a dying child shuts the stack down with no owned survivors,
// Ctrl-C (POSIX) exits 130 with freed ports, and port conflicts fail fast
// with an actionable message. Every case has a watchdog so a hung stack can
// never stall the suite.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createConnection } from "node:net";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { readProcessTreePids } from "../../packages/solver-contracts/src/scheduler.ts";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const stackScript = join(root, "scripts", "platform", "stack.mjs");

const READY_TIMEOUT_MS = "30000";
const GRACE_MS = "1000";

const apiStub = (port) => [
  "const http=require('node:http');",
  "require('node:fs').writeFileSync(process.argv[1],String(process.pid));",
  "let hits=0;",
  "const server=http.createServer((req,res)=>{",
  "if(req.url==='/health'){hits+=1;const ok=hits>2;res.writeHead(ok?200:500);res.end(ok?'{\"status\":\"ready\"}':'warming');return;}",
  `if(req.url==='/v1/native/capabilities'){res.writeHead(200);res.end('{"ready":[],"unavailable":[]}');return;}`,
  "res.writeHead(404);res.end('nope');});",
  `server.listen(${port},'127.0.0.1');`,
].join("");

const webStub = (port, delayMs) => [
  "const http=require('node:http');",
  "require('node:fs').writeFileSync(process.argv[1],String(process.pid));",
  `setTimeout(()=>{http.createServer((req,res)=>{res.writeHead(200);res.end('web');}).listen(${port},'127.0.0.1');},${delayMs});`,
  "setInterval(()=>{},1000);",
].join("");

const probeFree = (port) => new Promise((resolveProbe) => {
  const socket = createConnection({ host: "127.0.0.1", port }, () => {
    socket.destroy();
    resolveProbe(false);
  });
  socket.setTimeout(1000);
  socket.once("timeout", () => { socket.destroy(); resolveProbe(true); });
  socket.once("error", () => { socket.destroy(); resolveProbe(true); });
});

const pidGone = (pid) => {
  try {
    process.kill(pid, 0);
    return false;
  } catch {
    return true;
  }
};

const killPid = (pid) => {
  if (!Number.isInteger(pid) || pid <= 0 || pidGone(pid)) return;
  try {
    if (process.platform === "win32") {
      spawnSync("taskkill.exe", ["/PID", String(pid), "/F"], { stdio: "ignore" });
    } else {
      process.kill(pid, "SIGKILL");
    }
  } catch {
    // Best effort; the assertions below decide.
  }
};

const readPidFile = (path) => {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const pid = Number(readFileSync(path, "utf8").trim());
      if (Number.isInteger(pid) && pid > 0) return pid;
    } catch {
      // The stub writes its pid file on startup; poll briefly.
    }
    spawnSync(process.execPath, ["-e", "setTimeout(()=>{},100)"], { stdio: "ignore" });
  }
  throw new Error(`stub pid file never appeared: ${path}`);
};

const startStackProcess = (apiPort, webPort, extraEnv = {}) => {
  const scratch = mkdtempSync(join(tmpdir(), "aero-stack-live-"));
  const apiPidFile = join(scratch, "api.pid");
  const webPidFile = join(scratch, "web.pid");
  const child = spawn(process.execPath, [stackScript, "dev"], {
    cwd: root,
    shell: false,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      AERO_API_PORT: String(apiPort),
      AERO_WEB_PORT: String(webPort),
      AERO_STACK_READY_TIMEOUT_MS: READY_TIMEOUT_MS,
      AERO_STACK_STOP_GRACE_MS: GRACE_MS,
      AERO_STACK_API_COMMAND: JSON.stringify(["node", "-e", apiStub(apiPort), apiPidFile]),
      AERO_STACK_WEB_COMMAND: JSON.stringify(["node", "-e", webStub(webPort, 800), webPidFile]),
      ...extraEnv,
    },
  });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
  child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
  return {
    child,
    scratch,
    apiPidFile,
    webPidFile,
    output: () => `${stdout}\n${stderr}`,
    async waitReady() {
      const deadline = Date.now() + 60_000;
      for (;;) {
        if (stdout.includes("stack ready")) return;
        if (child.exitCode !== null || child.signalCode !== null) {
          throw new Error(`stack exited before ready (code ${child.exitCode}):\n${this.output()}`);
        }
        if (Date.now() > deadline) {
          throw new Error(`stack never reported ready:\n${this.output()}`);
        }
        await new Promise((resolveSleep) => setTimeout(resolveSleep, 200));
      }
    },
    waitExit(timeoutMs = 30_000) {
      return new Promise((resolveExit, rejectExit) => {
        if (child.exitCode !== null || child.signalCode !== null) {
          resolveExit(child.exitCode);
          return;
        }
        const timer = setTimeout(() => rejectExit(new Error(`stack did not exit:\n${this.output()}`)), timeoutMs);
        child.once("exit", (code) => { clearTimeout(timer); resolveExit(code); });
      });
    },
    cleanup() {
      try {
        if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
      } catch {
        // Already gone.
      }
      // Belt and braces: reap any owned descendants the stack left behind.
      try {
        for (const file of [apiPidFile, webPidFile]) {
          try {
            killPid(Number(readFileSync(file, "utf8").trim()));
          } catch {
            // Missing pid file means the stub never started.
          }
        }
      } finally {
        rmSync(scratch, { recursive: true, force: true });
      }
    },
  };
};

test("live stack reports ready only after gates respond, then cleans a dead child", async () => {
  const apiPort = 18081;
  const webPort = 13001;
  assert.equal(await probeFree(apiPort), true, `port ${apiPort} must be free for the live test`);
  assert.equal(await probeFree(webPort), true, `port ${webPort} must be free for the live test`);
  const stack = startStackProcess(apiPort, webPort);
  try {
    const startedAt = Date.now();
    await stack.waitReady();
    // The web stub listens ~800ms after spawn and the API stub 500s twice:
    // "ready" had to wait for real responses, not for spawn success.
    assert.ok(Date.now() - startedAt >= 700, `ready came too fast to be gate-verified:\n${stack.output()}`);
    assert.match(stack.output(), /stack ready: api=http:\/\/127\.0\.0\.1:18081/);
    const webPid = readPidFile(stack.webPidFile);
    const apiPid = readPidFile(stack.apiPidFile);
    assert.ok(!pidGone(webPid) && !pidGone(apiPid));
    killPid(webPid);
    const code = await stack.waitExit();
    assert.equal(code, 1, `unexpected child exit must shut the stack down with code 1:\n${stack.output()}`);
    assert.match(stack.output(), /web exited unexpectedly/);
    await new Promise((resolveSleep) => setTimeout(resolveSleep, 1500));
    assert.equal(await probeFree(apiPort), true, `api port ${apiPort} still held after shutdown`);
    assert.equal(await probeFree(webPort), true, `web port ${webPort} still held after shutdown`);
    assert.equal(pidGone(apiPid), true, "api stub survived the stack shutdown");
    assert.equal(pidGone(webPid), true, "web stub survived the stack shutdown");
  } finally {
    stack.cleanup();
  }
});

test("live stack fails fast with an actionable port-conflict error", async () => {
  const apiPort = 18082;
  const webPort = 13002;
  const holder = spawn(process.execPath, ["-e", `require('node:http').createServer((q,r)=>r.end('x')).listen(${apiPort},'127.0.0.1');setInterval(()=>{},1000);`],
    { shell: false, windowsHide: true, stdio: "ignore" });
  try {
    await new Promise((resolveSleep) => setTimeout(resolveSleep, 500));
    assert.equal(await probeFree(apiPort), false, "holder stub did not bind its port");
    const stack = startStackProcess(apiPort, webPort);
    try {
      const code = await stack.waitExit(60_000);
      assert.equal(code, 2, `port conflict must exit 2:\n${stack.output()}`);
      assert.match(stack.output(), new RegExp(`port ${apiPort} \\(local API\\) is occupied`));
      assert.match(stack.output(), /AERO_API_PORT/);
    } finally {
      stack.cleanup();
    }
  } finally {
    try {
      holder.kill("SIGKILL");
    } catch {
      // Already gone.
    }
  }
});

test("live stack names the failing component when the API command dies", async () => {
  const apiPort = 18083;
  const webPort = 13003;
  const stack = startStackProcess(apiPort, webPort, {
    AERO_STACK_API_COMMAND: JSON.stringify(["node", "-e", "process.exit(3)"]),
  });
  try {
    const code = await stack.waitExit(60_000);
    assert.equal(code, 1, `startup failure must exit 1:\n${stack.output()}`);
    assert.match(stack.output(), /STACK_STARTUP_FAILED:api/);
  } finally {
    stack.cleanup();
  }
});

test("live stack Ctrl-C leaves no owned child processes (POSIX)", { skip: process.platform === "win32" }, async () => {
  const apiPort = 18084;
  const webPort = 13004;
  const stack = startStackProcess(apiPort, webPort);
  try {
    await stack.waitReady();
    const apiPid = readPidFile(stack.apiPidFile);
    const webPid = readPidFile(stack.webPidFile);
    stack.child.kill("SIGINT");
    const code = await stack.waitExit();
    assert.equal(code, 130, `Ctrl-C must exit 130:\n${stack.output()}`);
    await new Promise((resolveSleep) => setTimeout(resolveSleep, 1500));
    assert.equal(await probeFree(apiPort), true, `api port ${apiPort} still held after Ctrl-C`);
    assert.equal(await probeFree(webPort), true, `web port ${webPort} still held after Ctrl-C`);
    assert.equal(pidGone(apiPid), true, "api stub survived Ctrl-C");
    assert.equal(pidGone(webPid), true, "web stub survived Ctrl-C");
    assert.equal(pidGone(stack.child.pid), true, "stack process survived Ctrl-C");
  } finally {
    stack.cleanup();
  }
});

test("live stack child-exit shutdown leaves no owned descendants on Windows", { skip: process.platform !== "win32" }, async () => {
  // A console Ctrl-C is delivered to the whole Windows console group and
  // cannot be simulated with kill(); the unexpected-exit path below exercises
  // the same reverse-order tree cleanup on this platform.
  const apiPort = 18085;
  const webPort = 13005;
  const stack = startStackProcess(apiPort, webPort);
  try {
    await stack.waitReady();
    const descendants = (await readProcessTreePids(stack.child.pid)).filter((pid) => pid !== stack.child.pid);
    assert.ok(descendants.length >= 2, `expected stub descendants, saw: ${descendants.join(",")}`);
    const webPid = readPidFile(stack.webPidFile);
    killPid(webPid);
    const code = await stack.waitExit();
    assert.equal(code, 1, `unexpected child exit must shut the stack down with code 1:\n${stack.output()}`);
    await new Promise((resolveSleep) => setTimeout(resolveSleep, 1500));
    for (const pid of descendants) {
      assert.equal(pidGone(pid), true, `owned descendant ${pid} survived the shutdown`);
    }
  } finally {
    stack.cleanup();
  }
});
