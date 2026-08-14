import json
from pathlib import Path

path = Path("domain-docs/ledger/ledger-set-dag.json")
bak = path.with_suffix(".json.bak")

data = json.loads(path.read_text(encoding="utf-8"))
bak.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Backup: {bak}")

# edges to remove (object -> function_tag)
REMOVE = {
    ("graphite_ledger", "fn_anchor"),
    ("relay_node", "fn_relay"),
    ("industrial_cloth", "fn_fuse"),
    ("signal_baton", "fn_break"),
    ("tri_key_clasp", "fn_span"),
    ("matte_coin", "fn_quiet"),
}

def endpoints(e):
    s = e.get("source") or e.get("from")
    t = e.get("target") or e.get("to")
    return s, t

before = len(data["edges"])
kept = []
removed = []
for e in data["edges"]:
    pair = endpoints(e)
    if pair in REMOVE:
        removed.append(pair)
    else:
        kept.append(e)

data["edges"] = kept
after = len(kept)

if "integrity" in data and "edge_count" in data["integrity"]:
    data["integrity"]["edge_count"] = after

path.write_text(json.dumps(data, indent=2), encoding="utf-8")

print(f"Edges: {before} -> {after} (removed {len(removed)})")
for s, t in removed:
    print(f"  removed {s} -> {t}")
if len(removed) != 6:
    print("WARNING: expected 6 removals")
else:
    print("OK — 6 isolation edges removed")