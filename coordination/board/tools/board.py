#!/usr/bin/env python3
"""tools/board.py — a lease-based task board for multi-agent work.

Reconstructed from the board protocol visible in @azizbuildss's reel screen recordings:
  claimTask / renewLease / completeTask / setAgentTarget / createEscalation / appendAudit
  plus heartbeat / reapExpired

The point of a LEASE rather than a simple claim: an agent that dies stops heartbeating, its lease
expires, and another agent can safely take the task. Without expiry a crashed worker blocks a task
forever; without a lease two workers duplicate it. Both failure modes are silent.

State lives in one JSON file so there is a single source of truth. All commands are idempotent
where that is meaningful and every mutation appends to the audit log.

Usage:
  board.py init
  board.py add <task-id> "<title>" --scope <path-prefix> [--scope ...]
  board.py claim <task-id> --agent <name> [--ttl 900]
  board.py renew <task-id> --agent <name> [--ttl 900]
  board.py heartbeat --agent <name>
  board.py complete <task-id> --agent <name> [--note "..."]
  board.py escalate <task-id> --agent <name> "<reason>"
  board.py release <task-id> --agent <name>
  board.py target <task-id> --agent <name>          # setAgentTarget: tag an owner
  board.py list [--status ready|claimed|done|escalated]
  board.py show <task-id>
  board.py reap                                    # expire dead leases
  board.py post --agent <name> "<message>"         # board message
  board.py read [--agent <name>] [--unread]
  board.py audit [-n 30]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

BOARD = Path(os.environ.get("BOARD_FILE", Path(__file__).resolve().parent.parent / "board.json"))
DEFAULT_TTL = 900  # 15 minutes


# ---------------------------------------------------------------- state
def load() -> dict:
    if not BOARD.exists():
        return {"tasks": {}, "messages": [], "audit": []}
    with BOARD.open(encoding="utf-8") as fh:
        return json.load(fh)


def save(state: dict) -> None:
    tmp = BOARD.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    tmp.replace(BOARD)


def audit(state: dict, who: str, action: str, detail: str) -> None:
    state["audit"].append(
        {"ts": time.time(), "iso": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": who,
         "action": action, "detail": detail}
    )


def now() -> float:
    return time.time()


def lease_live(task: dict) -> bool:
    le = task.get("lease")
    return bool(le) and le.get("expires_at", 0) > now()


def reap_expired(state: dict, who: str = "system") -> list[str]:
    """Expire dead leases so a crashed worker cannot block a task forever."""
    reaped = []
    for tid, t in state["tasks"].items():
        if t.get("status") == "claimed" and not lease_live(t):
            prev = (t.get("lease") or {}).get("agent", "?")
            t["status"] = "ready"
            t["lease"] = None
            t["reap_count"] = t.get("reap_count", 0) + 1
            audit(state, who, "reap", f"{tid} lease expired, was held by {prev}")
            reaped.append(tid)
    return reaped


def require(state: dict, tid: str) -> dict:
    if tid not in state["tasks"]:
        sys.exit(f"no such task: {tid}")
    return state["tasks"][tid]


def check_holder(task: dict, agent: str) -> None:
    le = task.get("lease") or {}
    if le.get("agent") != agent:
        sys.exit(f"task held by {le.get('agent')!r}, not {agent!r}")
    if not lease_live(task):
        sys.exit("lease expired — run reap, then claim again")


# ---------------------------------------------------------------- commands
def cmd_init(args):
    if BOARD.exists() and not args.force:
        sys.exit(f"{BOARD} exists (use --force)")
    save({"tasks": {}, "messages": [], "audit": []})
    print(f"initialised {BOARD}")


def cmd_add(args):
    st = load()
    if args.task_id in st["tasks"]:
        sys.exit(f"task exists: {args.task_id}")
    st["tasks"][args.task_id] = {
        "id": args.task_id, "title": args.title, "scopes": args.scope or [],
        "status": "ready", "lease": None, "target": None, "notes": [],
        "escalation": None, "created": now(),
    }
    audit(st, args.agent, "add", args.task_id)
    save(st)
    print(f"added {args.task_id}")


def cmd_claim(args):
    st = load()
    reap_expired(st)
    t = require(st, args.task_id)
    if t["status"] == "done":
        sys.exit("already done")
    if lease_live(t):
        sys.exit(f"held by {t['lease']['agent']} until {time.strftime('%H:%M:%S', time.localtime(t['lease']['expires_at']))}")
    # write-scope collision check: two live claims must not share a scope
    mine = set(t.get("scopes") or [])
    for oid, o in st["tasks"].items():
        if oid == args.task_id or not lease_live(o):
            continue
        clash = mine & set(o.get("scopes") or [])
        if clash:
            sys.exit(f"scope collision with {oid} ({o['lease']['agent']}) on {sorted(clash)}")
    t["status"] = "claimed"
    t["lease"] = {"agent": args.agent, "token": uuid.uuid4().hex[:8],
                  "expires_at": now() + args.ttl}
    audit(st, args.agent, "claim", f"{args.task_id} ttl={args.ttl}")
    save(st)
    print(f"claimed {args.task_id} token={t['lease']['token']} ttl={args.ttl}s")


def cmd_renew(args):
    st = load()
    t = require(st, args.task_id)
    check_holder(t, args.agent)
    t["lease"]["expires_at"] = now() + args.ttl
    audit(st, args.agent, "renew", args.task_id)
    save(st)
    print(f"renewed {args.task_id} until {time.strftime('%H:%M:%S', time.localtime(t['lease']['expires_at']))}")


def cmd_heartbeat(args):
    st = load()
    n = 0
    for t in st["tasks"].values():
        if t.get("lease") and t["lease"].get("agent") == args.agent and lease_live(t):
            t["lease"]["expires_at"] = now() + args.ttl
            n += 1
    reap_expired(st)
    save(st)
    print(f"renewed {n} lease(s) for {args.agent}")


def cmd_complete(args):
    st = load()
    t = require(st, args.task_id)
    check_holder(t, args.agent)
    t["status"] = "done"
    if args.note:
        t["notes"].append(args.note)
    t["lease"] = None
    t["completed"] = now()
    audit(st, args.agent, "complete", f"{args.task_id} {args.note or ''}".strip())
    save(st)
    print(f"completed {args.task_id}")


def cmd_release(args):
    st = load()
    t = require(st, args.task_id)
    check_holder(t, args.agent)
    t["status"] = "ready"
    t["lease"] = None
    audit(st, args.agent, "release", args.task_id)
    save(st)
    print(f"released {args.task_id}")


def cmd_escalate(args):
    st = load()
    t = require(st, args.task_id)
    t["status"] = "escalated"
    t["escalation"] = {"by": args.agent, "reason": args.reason, "ts": now()}
    audit(st, args.agent, "escalate", f"{args.task_id}: {args.reason}")
    save(st)
    print(f"escalated {args.task_id}")


def cmd_target(args):
    st = load()
    t = require(st, args.task_id)
    t["target"] = args.agent
    audit(st, "lead", "setAgentTarget", f"{args.task_id} -> {args.agent}")
    save(st)
    print(f"{args.task_id} targeted at {args.agent}")


def cmd_reap(args):
    st = load()
    r = reap_expired(st)
    save(st)
    print(f"reaped {len(r)}: {', '.join(r) if r else '(none)'}")


def cmd_list(args):
    st = load()
    reap_expired(st)
    rows = [t for t in st["tasks"].values() if not args.status or t["status"] == args.status]
    if not rows:
        print("(no tasks)")
        return
    print(f"{'task':22s} {'status':10s} {'holder':16s} {'ttl':>6s}  scopes")
    for t in sorted(rows, key=lambda x: x["id"]):
        le = t.get("lease") or {}
        ttl = ""
        if le and lease_live(t):
            ttl = f"{int(le['expires_at'] - now())}s"
        print(f"{t['id'][:22]:22s} {t['status']:10s} {(le.get('agent') or '-')[:16]:16s} "
              f"{ttl:>6s}  {','.join(t.get('scopes') or []) or '-'}")
    save(st)


def cmd_show(args):
    st = load()
    print(json.dumps(require(st, args.task_id), indent=2))


def cmd_post(args):
    st = load()
    st["messages"].append({"id": len(st["messages"]) + 1, "agent": args.agent,
                           "text": args.message, "ts": now(),
                           "iso": time.strftime("%H:%M:%S")})
    audit(st, args.agent, "post", args.message[:80])
    save(st)
    print("posted")


def cmd_read(args):
    st = load()
    cursor = BOARD.with_suffix(".cursor")
    n = 0
    last = 0
    if cursor.exists():
        try:
            last = int(cursor.read_text().strip() or 0)
        except ValueError:
            last = 0
    for m in st["messages"]:
        if args.unread and m["id"] <= last:
            continue
        if args.agent and m["agent"] != args.agent:
            continue
        print(f"[{m['iso']}] {m['agent']}: {m['text']}")
        n = max(n, m["id"])
    if args.unread and n:
        cursor.write_text(str(n))
    if n == 0:
        print("(no messages)")


def cmd_audit(args):
    st = load()
    for a in st["audit"][-args.n:]:
        print(f"[{a['iso']}] {a['agent']:16s} {a['action']:14s} {a['detail']}")


def main() -> int:
    p = argparse.ArgumentParser(description="lease-based task board")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_init)

    s = sub.add_parser("add")
    s.add_argument("task_id"); s.add_argument("title")
    s.add_argument("--scope", action="append"); s.add_argument("--agent", default="lead")
    s.set_defaults(fn=cmd_add)

    for name, fn in (("claim", cmd_claim), ("renew", cmd_renew)):
        s = sub.add_parser(name)
        s.add_argument("task_id"); s.add_argument("--agent", required=True)
        s.add_argument("--ttl", type=int, default=DEFAULT_TTL); s.set_defaults(fn=fn)

    s = sub.add_parser("heartbeat")
    s.add_argument("--agent", required=True)
    s.add_argument("--ttl", type=int, default=DEFAULT_TTL); s.set_defaults(fn=cmd_heartbeat)

    s = sub.add_parser("complete")
    s.add_argument("task_id"); s.add_argument("--agent", required=True)
    s.add_argument("--note", default=""); s.set_defaults(fn=cmd_complete)

    s = sub.add_parser("release")
    s.add_argument("task_id"); s.add_argument("--agent", required=True); s.set_defaults(fn=cmd_release)

    s = sub.add_parser("escalate")
    s.add_argument("task_id"); s.add_argument("--agent", required=True); s.add_argument("reason")
    s.set_defaults(fn=cmd_escalate)

    s = sub.add_parser("target")
    s.add_argument("task_id"); s.add_argument("--agent", required=True); s.set_defaults(fn=cmd_target)

    s = sub.add_parser("reap"); s.set_defaults(fn=cmd_reap)

    s = sub.add_parser("list"); s.add_argument("--status"); s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show"); s.add_argument("task_id"); s.set_defaults(fn=cmd_show)

    s = sub.add_parser("post")
    s.add_argument("--agent", required=True); s.add_argument("message"); s.set_defaults(fn=cmd_post)

    s = sub.add_parser("read")
    s.add_argument("--agent"); s.add_argument("--unread", action="store_true"); s.set_defaults(fn=cmd_read)

    s = sub.add_parser("audit"); s.add_argument("-n", type=int, default=30); s.set_defaults(fn=cmd_audit)

    args = p.parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())