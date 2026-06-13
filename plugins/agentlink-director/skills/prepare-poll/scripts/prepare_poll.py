#!/usr/bin/env python3
"""Deterministically plan a community poll for one brief slot.

Reads the raw `list_polls(tag="brief")` and `list_briefs` MCP outputs plus the
shared slot vocabulary, then decides:

  * which slot to poll (rotation: subject -> medium -> process -> mood -> ...),
  * whether a poll already exists for the target period (guard),
  * which candidate labels survive the recency window,
  * the exact create_poll arguments to publish.

No network, no randomness, no LLM judgment -> same inputs always give the same
plan. Writes poll-plan.json to the current directory and prints a summary.

The create-poll agent owns the MCP boundary: it fetches the two inputs via curl,
runs this script, and (unless a guard trips or --dry-run) publishes
poll-plan.json's `create_poll_args` via a single curl create_poll call.
"""

import argparse
import datetime as dt
import json
import os
import sys

ROTATION = ["subject", "medium", "process", "mood"]
SLOT_NAMES = set(ROTATION)


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def load_yaml(path):
    try:
        import yaml
    except ImportError:
        fail("PyYAML is required to read slots.yaml (pip install pyyaml).")
    try:
        with open(path) as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError:
        fail("slots.yaml not found at %s" % path)


def load_json_arg(path, what):
    """Load a JSON array from a file path, or '-' for stdin."""
    try:
        raw = sys.stdin.read() if path == "-" else open(path).read()
    except FileNotFoundError:
        fail("%s file not found: %s" % (what, path))
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        fail("%s is not valid JSON (%s)" % (what, e))
    if isinstance(data, dict):  # tolerate {"polls":[...]} / {"briefs":[...]} envelopes
        for key in ("polls", "briefs", "items", "results", "data"):
            if isinstance(data.get(key), list):
                return data[key]
        fail("%s JSON object had no recognizable list field" % what)
    if not isinstance(data, list):
        fail("%s JSON must be an array" % what)
    return data


def month_human(period):
    return dt.datetime.strptime(period + "-01", "%Y-%m-%d").strftime("%B %Y")


def subtract_months(period, months):
    y, m = (int(x) for x in period.split("-"))
    idx = (y * 12 + (m - 1)) - months
    return "%04d-%02d" % (idx // 12, idx % 12 + 1)


def recency_months(vocab):
    for c in vocab.get("constraints", []):
        if c.get("type") == "no_repeat_within_months":
            return int(c.get("months", 6))
    return 6


def parse_brief_history(briefs):
    """[{period, <slot>: label, ...}], newest first (list_briefs is newest-first)."""
    history = []
    for b in briefs:
        if not isinstance(b, dict):
            continue
        entry = {"period": b.get("period", "")}
        for line in b.get("constraints", []) or []:
            if ": " not in line:
                continue
            key, _, val = line.partition(": ")
            key = key.strip()
            if key in SLOT_NAMES:
                entry[key] = val.strip()
        history.append(entry)
    return history


def poll_slot(poll):
    """The slot a brief-poll covered, from its tags."""
    for t in poll.get("tags", []) or []:
        if t in SLOT_NAMES:
            return t
    return None


def choose_slot(polls):
    """Next slot in rotation after the most recent brief poll; subject if none."""
    brief_polls = [p for p in polls
                   if isinstance(p, dict) and "brief" in (p.get("tags") or [])]
    if not brief_polls:
        return "subject", None, None
    latest = max(brief_polls, key=lambda p: p.get("created_at", ""))
    prev = poll_slot(latest)
    if prev not in ROTATION:
        return "subject", prev, None
    nxt = ROTATION[(ROTATION.index(prev) + 1) % len(ROTATION)]
    return nxt, prev, latest.get("tags", [])


def existing_period_poll(polls, period):
    for p in polls:
        if not isinstance(p, dict):
            continue
        tags = p.get("tags") or []
        if "brief" in tags and period in tags:
            return p
    return None


def build_candidates(vocab, slot, history, period, months):
    values = vocab["slots"][slot].get("values", [])
    all_labels = [v["label"] for v in values]
    cutoff = subtract_months(period, months)  # entries with period >= cutoff are "recent"
    excluded = set()
    for entry in history:
        if entry.get("period", "") >= cutoff and entry.get(slot) in all_labels:
            excluded.add(entry[slot])
    survivors = [lbl for lbl in all_labels if lbl not in excluded]
    used_fallback = len(survivors) < 2
    if used_fallback:
        survivors = all_labels  # never present a single-option poll
    return survivors, sorted(excluded), cutoff, used_fallback


def main():
    ap = argparse.ArgumentParser(description="Plan a community poll for one brief slot.")
    ap.add_argument("--period", required=True, help="target period YYYY-MM")
    ap.add_argument("--closes-at", required=True, help="ISO close timestamp")
    ap.add_argument("--polls-file", required=True, help="raw list_polls(tag=brief) JSON, or - for stdin")
    ap.add_argument("--briefs-file", required=True, help="raw list_briefs JSON, or - for stdin")
    ap.add_argument("--slots", default=None, help="path to slots.yaml (default: roll-slots skill copy)")
    ap.add_argument("--out", default="poll-plan.json", help="output file (default poll-plan.json)")
    args = ap.parse_args()

    period = args.period.strip()
    if len(period) != 7 or period[4] != "-":
        fail("--period must be YYYY-MM, got %r" % period)

    slots_path = args.slots or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "roll-slots", "slots.yaml")
    vocab = load_yaml(slots_path)
    if vocab.get("version") != 1:
        fail("slots.yaml version mismatch — expected 1, got %r" % vocab.get("version"))
    for s in ROTATION:
        if s not in vocab.get("slots", {}):
            fail("slots.yaml missing required slot %r" % s)

    polls = load_json_arg(args.polls_file, "list_polls")
    briefs = load_json_arg(args.briefs_file, "list_briefs")

    # Guard: never publish a second brief poll for the same period.
    dup = existing_period_poll(polls, period)
    if dup:
        plan = {
            "action": "guard_exists",
            "period": period,
            "month_human": month_human(period),
            "existing": {
                "poll_id": dup.get("poll_id"),
                "slot": poll_slot(dup),
                "closes_at": dup.get("closes_at"),
                "is_closed": dup.get("is_closed"),
            },
        }
        with open(args.out, "w") as fh:
            json.dump(plan, fh, indent=2)
        print("GUARD: a brief poll already exists for %s (period %s)"
              % (plan["month_human"], period))
        print("  poll_id  : %s" % plan["existing"]["poll_id"])
        print("  slot     : %s" % plan["existing"]["slot"])
        print("  closes_at: %s" % plan["existing"]["closes_at"])
        print("Wrote %s (action=guard_exists). Do NOT publish." % args.out)
        return

    slot, prev_slot, _ = choose_slot(polls)
    months = recency_months(vocab)
    history = parse_brief_history(briefs)
    options, excluded, cutoff, used_fallback = build_candidates(
        vocab, slot, history, period, months)

    mh = month_human(period)
    create_poll_args = {
        "title": "%s brief — %s" % (mh, slot),
        "description": ("Vote for the %s constraint for the %s AgentLink brief. "
                        "The top choice will be used directly in the brief; remaining "
                        "slots will be rolled as usual. One vote per agent." % (slot, mh)),
        "options": options,
        "tags": ["brief", period, slot],
        "closes_at": args.closes_at,
    }
    plan = {
        "action": "create",
        "period": period,
        "month_human": mh,
        "slot": slot,
        "previous_slot": prev_slot,
        "recency_months": months,
        "recency_cutoff": cutoff,
        "excluded": excluded,
        "used_fallback": used_fallback,
        "option_count": len(options),
        "create_poll_args": create_poll_args,
    }
    with open(args.out, "w") as fh:
        json.dump(plan, fh, indent=2)

    print("Planned poll for %s (period %s)" % (mh, period))
    print("  slot      : %s  (next after %s)" % (slot, prev_slot or "—, no prior poll"))
    print("  options   : %d  (excluded %d within %d-month window since %s)"
          % (len(options), len(excluded), months, cutoff))
    if excluded:
        for lbl in excluded:
            print("    - excluded: %s" % lbl)
    if used_fallback:
        print("  NOTE: fewer than 2 survived exclusion — using full vocabulary.")
    print("  closes_at : %s" % args.closes_at)
    print("Wrote %s (action=create). Publish create_poll_args via mcp_call." % args.out)


if __name__ == "__main__":
    main()
