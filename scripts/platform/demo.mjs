const demo = process.argv[2];
if (!new Set(["edf", "aircraft", "gas-turbine"]).has(demo)) {
  console.error("Usage: node scripts/platform/demo.mjs <edf|aircraft|gas-turbine>");
  process.exit(64);
}
console.error(`DEMO_NOT_STARTED: ${demo} requires explicit case data and READY native solver capabilities. No synthetic result was emitted.`);
process.exit(2);
