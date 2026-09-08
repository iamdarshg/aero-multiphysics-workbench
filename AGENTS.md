# Engineering rules

- Never fabricate solver output. Every numerical result must record whether it came from an analytical model, surrogate, benchmark, or native solver execution.
- Fail closed when a requested native capability is unavailable.
- Keep the aggregate RSS of project-owned local processes below 1 GB. Prefer bounded test runs and single-worker execution.
- Keep modules focused and contracts typed.
- Add tests before implementation for new behavior.
- Do not edit another workstream's declared ownership area.
- Use Chrome or the built-in browser for browser testing; do not use Firefox or Floorp.

