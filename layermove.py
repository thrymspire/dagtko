import json
from pathlib import Path

path = Path("domain-docs/ledger/ledger-set-dag.json")
bak = path.with_suffix(".json.bak-layer")
data = json.loads(path.read_text(encoding="utf-8"))
bak.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Backup: {bak}")

MOVES = {
    "symbol_tri_span": 3,
    "symbol_blank_coin": 3,
}
# Optional label fix (comment out to skip):
# RELABEL = {"sec_ledger_set": "Ledger Registry"}
RELABEL = {}

changed = []
for n in data["nodes"]:
    i = n.get("id")
    if i in MOVES:
        old = n.get("layer")
        n["layer"] = MOVES[i]
        changed.append(f"{i}: layer {old} -> {MOVES[i]}")
    if i in RELABEL:
        old = n.get("label")
        n["label"] = RELABEL[i]
        changed.append(f"{i}: label {old!r} -> {RELABEL[i]!r}")

path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("Changes:")
for c in changed:
    print(" ", c)
print("OK" if len(changed) >= 2 else "WARNING: expected at least 2 layer moves")
