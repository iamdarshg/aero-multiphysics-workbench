import { CAPABILITY_MANIFESTS, CapabilityDetector, commandProbe } from "../../packages/solver-contracts/src/index.ts";

const report = await new CapabilityDetector(commandProbe).detect(CAPABILITY_MANIFESTS);
console.log(JSON.stringify(report, null, 2));
process.exitCode = report.unavailable.length === 0 ? 0 : 2;
