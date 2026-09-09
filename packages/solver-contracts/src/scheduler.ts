import { spawn, type ChildProcess } from "node:child_process";
import { readdir, readFile } from "node:fs/promises";
import { isAbsolute, relative, resolve } from "node:path";
import type { JobRequest, LocalProcessResult, ScheduledJob } from "./contracts.ts";

/** The project budget is deliberately below the one-gigabyte host contract. */
export const DEFAULT_LOCAL_RSS_BUDGET_MIB = 896;

export interface SchedulerPolicy {
  readonly aggregateRssMiB?: number;
  readonly remoteComputeAuthorized?: boolean;
  readonly remainingRemoteBudgetUsd?: number;
}

export interface LocalRunPolicy {
  readonly allowedExecutables: ReadonlySet<string>;
  readonly allowedArguments?: (args: readonly string[]) => boolean;
  readonly pollIntervalMs?: number;
  readonly timeoutMs?: number;
  readonly signal?: AbortSignal;
  readonly workingDirectory?: string;
  readonly allowedWorkingDirectory?: string;
  /** Test seam and platform-specific override. It must include descendants. */
  readonly readRssMiB?: (pid: number) => Promise<number>;
}

const delay = (milliseconds: number): Promise<void> => new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));

const readCommandOutput = (command: string, args: readonly string[]): Promise<string> => new Promise((resolveOutput, reject) => {
  const child = spawn(command, [...args], { shell: false, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  let stdout = "";
  let stderr = "";
  child.stdout?.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
  child.stderr?.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });
  child.once("error", reject);
  child.once("close", (code) => code === 0 ? resolveOutput(stdout) : reject(new Error(stderr.trim() || `RSS probe exited ${code}`)));
});

const linuxProcessTable = async (): Promise<Map<number, { parent: number; rssMiB: number }>> => {
  const entries = await readdir("/proc", { withFileTypes: true });
  const table = new Map<number, { parent: number; rssMiB: number }>();
  await Promise.all(entries.filter((entry) => /^\d+$/.test(entry.name)).map(async (entry) => {
    const pid = Number(entry.name);
    try {
      const stat = await readFile(`/proc/${pid}/stat`, "utf8");
      const closeParen = stat.lastIndexOf(")");
      const fields = stat.slice(closeParen + 2).split(" ");
      const parent = Number(fields[1]);
      const status = await readFile(`/proc/${pid}/status`, "utf8");
      const rss = /^VmRSS:\s+(\d+)\s+kB$/m.exec(status);
      if (Number.isInteger(parent) && rss) table.set(pid, { parent, rssMiB: Number(rss[1]) / 1024 });
    } catch {
      // Processes can disappear while the table is being read.
    }
  }));
  return table;
};

const sumProcessTree = (rootPid: number, table: ReadonlyMap<number, { parent: number; rssMiB: number }>): number => {
  const children = new Map<number, number[]>();
  for (const [pid, row] of table) children.set(row.parent, [...(children.get(row.parent) ?? []), pid]);
  const seen = new Set<number>();
  const pending = [rootPid];
  let total = 0;
  while (pending.length > 0) {
    const pid = pending.pop() as number;
    if (seen.has(pid)) continue;
    seen.add(pid);
    const row = table.get(pid);
    if (!row) {
      if (pid === rootPid) throw new Error("RSS_ROOT_NOT_REPORTED");
      continue;
    }
    total += row.rssMiB;
    pending.push(...(children.get(pid) ?? []));
  }
  return total;
};

/** Reads aggregate RSS for the root and every descendant without a shell. */
export const readProcessTreeRssMiB = async (rootPid: number): Promise<number> => {
  if (!Number.isInteger(rootPid) || rootPid <= 0) throw new Error("INVALID_PROCESS_ID");
  if (process.platform === "linux") return sumProcessTree(rootPid, await linuxProcessTable());
  if (process.platform === "win32") {
    const systemRoot = process.env.SystemRoot ?? "C:\\Windows";
    const powershell = `${systemRoot}\\System32\\WindowsPowerShell\\v1.0\\powershell.exe`;
    // The only interpolated value is an integer validated above. No user
    // command or path is interpreted by this probe.
    const script = `$root=${rootPid};$p=Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId;` +
      "$ids=@($root);do{$added=$false;foreach($x in $p){if($ids -contains [int]$x.ParentProcessId -and $ids -notcontains [int]$x.ProcessId){$ids+=[int]$x.ProcessId;$added=$true}}}while($added);" +
      "$sum=0;foreach($id in $ids){try{$sum+=(Get-Process -Id $id -ErrorAction Stop).WorkingSet64}catch{if($id -eq $root){exit 2}}};[Console]::WriteLine($sum)";
    const bytes = await readCommandOutput(powershell, ["-NoProfile", "-NonInteractive", "-Command", script]);
    const total = Number(bytes.trim());
    if (!Number.isFinite(total) || total < 0) throw new Error("RSS_NOT_REPORTED");
    return total / 1024 / 1024;
  }
  const rows = await readCommandOutput("ps", ["-axo", "pid=,ppid=,rss="]);
  const table = new Map<number, { parent: number; rssMiB: number }>();
  for (const line of rows.split(/\r?\n/)) {
    const match = /^\s*(\d+)\s+(\d+)\s+(\d+)\s*$/.exec(line);
    if (match) table.set(Number(match[1]), { parent: Number(match[2]), rssMiB: Number(match[3]) / 1024 });
  }
  return sumProcessTree(rootPid, table);
};

/** Backwards-compatible name; it now includes descendants. */
export const readProcessRssMiB = readProcessTreeRssMiB;

const executableMatches = (actual: string, allowed: string): boolean => process.platform === "win32"
  ? actual.toLowerCase() === allowed.toLowerCase()
  : actual === allowed;

const hasUnsafeArgument = (arg: string): boolean => arg.includes("\u0000") || /[\r\n]/.test(arg) || /^(?:-Command|-EncodedCommand)$/i.test(arg);

const pathIsContained = (root: string, candidate: string): boolean => {
  const remainder = relative(resolve(root), resolve(candidate));
  return remainder === "" || (remainder !== ".." && !remainder.startsWith(`..${candidate.includes("\\") ? "\\" : "/"}`) && !isAbsolute(remainder));
};

const waitForExit = (child: ChildProcess): Promise<number | null> => new Promise((resolveExit, reject) => {
  child.once("error", reject);
  child.once("exit", (code) => resolveExit(code));
});

const terminateTree = async (child: ChildProcess): Promise<void> => {
  if (!child.pid || child.exitCode !== null) return;
  if (process.platform === "win32") {
    try { await readCommandOutput("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"]); } catch { /* process may have exited */ }
    return;
  }
  try { process.kill(-child.pid, "SIGKILL"); } catch { try { child.kill("SIGKILL"); } catch { /* process may have exited */ } }
};

/** Reservation scheduler plus a fail-closed local process supervisor. */
export class LocalScheduler {
  private readonly jobs = new Map<string, ScheduledJob>();
  private readonly aggregateRssMiB: number;
  private readonly remoteComputeAuthorized: boolean;
  private remoteBudget: number;

  constructor(policy: SchedulerPolicy = {}) {
    this.aggregateRssMiB = policy.aggregateRssMiB ?? DEFAULT_LOCAL_RSS_BUDGET_MIB;
    if (!Number.isFinite(this.aggregateRssMiB) || this.aggregateRssMiB <= 0 || this.aggregateRssMiB > DEFAULT_LOCAL_RSS_BUDGET_MIB) throw new Error("INVALID_RSS_BUDGET");
    this.remoteComputeAuthorized = policy.remoteComputeAuthorized ?? false;
    this.remoteBudget = policy.remainingRemoteBudgetUsd ?? 0;
    if (!Number.isFinite(this.remoteBudget) || this.remoteBudget < 0) throw new Error("INVALID_REMOTE_BUDGET");
  }

  submit(request: JobRequest): ScheduledJob {
    if (!request.id || !Number.isFinite(request.requestedMemoryMiB) || request.requestedMemoryMiB <= 0 || request.requestedMemoryMiB > this.aggregateRssMiB) throw new Error("INVALID_RSS_RESERVATION");
    if (!Number.isFinite(request.costCeilingUsd) || request.costCeilingUsd < 0) throw new Error("INVALID_COST_CEILING");
    if (this.jobs.has(request.id)) throw new Error("DUPLICATE_JOB_ID");
    if (request.remote && !this.remoteComputeAuthorized) throw new Error("REMOTE_COMPUTE_NOT_AUTHORIZED");
    if (request.remote && request.costCeilingUsd > this.remoteBudget) throw new Error("REMOTE_COST_BUDGET_EXCEEDED");
    const committed = [...this.jobs.values()].reduce((total, job) => total + job.requestedMemoryMiB, 0);
    if (committed + request.requestedMemoryMiB > this.aggregateRssMiB) throw new Error("RSS_BUDGET_EXCEEDED");
    if (request.remote) this.remoteBudget -= request.costCeilingUsd;
    const job = { ...request, state: "queued" as const };
    this.jobs.set(job.id, job);
    return job;
  }

  snapshot(): readonly ScheduledJob[] { return [...this.jobs.values()]; }

  cancel(id: string, ownerId?: string): ScheduledJob {
    const job = this.jobs.get(id);
    if (!job) throw new Error("JOB_NOT_FOUND");
    if (job.ownerId !== ownerId) throw new Error("JOB_NOT_OWNED");
    this.jobs.delete(id);
    return job;
  }

  async runLocal(request: JobRequest, command: readonly string[], policy: LocalRunPolicy): Promise<LocalProcessResult> {
    const [executable, ...args] = command;
    if (!executable || ![...policy.allowedExecutables].some((allowed) => executableMatches(executable, allowed))) throw new Error("COMMAND_NOT_ALLOWLISTED");
    if (args.some(hasUnsafeArgument) || policy.allowedArguments?.(args) === false) throw new Error("ARGUMENTS_NOT_ALLOWLISTED");
    if (request.remote) throw new Error("LOCAL_RUN_CANNOT_BE_REMOTE");
    const cwd = policy.workingDirectory ? resolve(policy.workingDirectory) : undefined;
    if (cwd && policy.allowedWorkingDirectory && !pathIsContained(policy.allowedWorkingDirectory, cwd)) throw new Error("WORKING_DIRECTORY_OUTSIDE_ALLOWLIST");
    if (cwd && !policy.allowedWorkingDirectory) throw new Error("WORKING_DIRECTORY_ROOT_REQUIRED");
    if (policy.timeoutMs !== undefined && (!Number.isFinite(policy.timeoutMs) || policy.timeoutMs <= 0)) throw new Error("INVALID_PROCESS_TIMEOUT");

    this.submit(request);
    let child: ChildProcess | undefined;
    let peakRssMiB = 0;
    let exit: Promise<number | null> | undefined;
    try {
      child = spawn(executable, args, { shell: false, windowsHide: true, detached: process.platform !== "win32", cwd, stdio: "ignore" });
      if (!child.pid) return { state: "failed", exitCode: null, peakRssMiB, reason: "PROCESS_START_FAILED" };
      exit = waitForExit(child);
      const readRss = policy.readRssMiB ?? readProcessTreeRssMiB;
      const interval = Math.max(1, policy.pollIntervalMs ?? 100);
      const started = Date.now();
      let sampled = false;
      while (child.exitCode === null && !child.killed) {
        if (policy.signal?.aborted) {
          await terminateTree(child);
          await exit;
          return { state: "failed", exitCode: child.exitCode, peakRssMiB, reason: "PROCESS_CANCELLED" };
        }
        if (policy.timeoutMs !== undefined && Date.now() - started >= policy.timeoutMs) {
          await terminateTree(child);
          await exit;
          return { state: "failed", exitCode: child.exitCode, peakRssMiB, reason: "PROCESS_TIMEOUT" };
        }
        try {
          const rssMiB = await readRss(child.pid);
          if (!Number.isFinite(rssMiB) || rssMiB < 0) throw new Error("INVALID_RSS_SAMPLE");
          sampled = true;
          peakRssMiB = Math.max(peakRssMiB, rssMiB);
          if (rssMiB > this.aggregateRssMiB || rssMiB > request.requestedMemoryMiB) {
            await terminateTree(child);
            await exit;
            return { state: "failed", exitCode: child.exitCode, peakRssMiB, reason: "PROCESS_RSS_LIMIT_EXCEEDED" };
          }
        } catch {
          if (child.exitCode !== null) break;
          await terminateTree(child);
          await exit;
          return { state: "failed", exitCode: child.exitCode, peakRssMiB, reason: "RSS_MONITOR_UNAVAILABLE" };
        }
        await delay(interval);
      }
      const exitCode = child.exitCode ?? await exit;
      if (!sampled) return { state: "failed", exitCode, peakRssMiB, reason: "RSS_MONITOR_UNAVAILABLE" };
      return exitCode === 0 ? { state: "completed", exitCode, peakRssMiB } : { state: "failed", exitCode, peakRssMiB, reason: "PROCESS_EXIT_NONZERO" };
    } catch (error) {
      if (child) await terminateTree(child);
      if (exit) await exit.catch(() => undefined);
      if (error instanceof Error && error.message === "INVALID_PROCESS_TIMEOUT") throw error;
      return { state: "failed", exitCode: child?.exitCode ?? null, peakRssMiB, reason: "PROCESS_START_FAILED" };
    } finally {
      if (child) await terminateTree(child);
      this.jobs.delete(request.id);
    }
  }
}
