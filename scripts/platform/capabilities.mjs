// Native capability report. The probe cache makes repeated queries within one
// process warm: `--repeat N` exercises it and reports the probe/hit split on
// stderr (stdout stays the plain capability report consumed by bootstrap.mjs).
import { CAPABILITY_MANIFESTS, CapabilityProbeCache, commandProbe } from "../../packages/solver-contracts/src/index.ts";

const args = process.argv.slice(2);
const repeatFlag = args.indexOf("--repeat");
const repeat = repeatFlag >= 0 ? Math.max(1, Number.parseInt(args[repeatFlag + 1] ?? "1", 10) || 1) : 1;

const cache = new CapabilityProbeCache({ probe: commandProbe });
const started = Date.now();
let report;
for (let index = 0; index < repeat; index += 1) report = await cache.detect(CAPABILITY_MANIFESTS);
const elapsedMs = Date.now() - started;

console.log(JSON.stringify(report, null, 2));
if (repeat > 1) {
  const stats = cache.stats();
  console.error(`[capabilities] repeat=${repeat} elapsed=${elapsedMs}ms probes=${stats.probes} hits=${stats.hits}`);
}
process.exitCode = report.unavailable.length === 0 ? 0 : 2;
