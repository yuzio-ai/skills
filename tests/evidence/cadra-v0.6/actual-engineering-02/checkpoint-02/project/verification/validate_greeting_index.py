"""Validate one prepared delivery; no stage selection or scheduling."""
import json
import sys
from pathlib import Path

from record_io import now, read, sha

pending = Path(sys.argv[1])
expected = json.loads(Path(sys.argv[2]).read_text())
data, body = read(pending)
assert data == expected["contract"]
assert data["contract"] == "0.8" and data["task"] == expected["task"]
assert data["execution_mode"] == "unattended"
assert data["stage_result"] == {"stage": expected["stage"], "status": "completed", "round": expected["round"]}
assert type(data["stage_result"]["round"]) is int and expected["round"] > 0
assert data["candidate"] == expected["candidate"]
assert data["status"] == "in_progress"
assert data["blocked"] == {"value": False, "reason": None}
assert data["next"] == {"stage": "review", "allowed": True, "reason": "stage_completed"}
handoff = Path(expected["handoff"])
assert sha(handoff) == expected["handoff_sha256"]
assert data["candidate"]["snapshot"] == str(handoff)
assert handoff.name == f"{expected['stage']}-{expected['round']:02d}.md"
text = handoff.read_text()
for required in ("cohestra v0.8", "0.10.1", "unattended", "阶段 code，轮次 1", "$cohestra review", "5 tests passed"):
    assert required in text
assert handoff.name in body and "独立审查和正式验收未执行" in body
manifest_path = pending.parent / "candidate-01/manifest.json"
assert sha(manifest_path) == expected["candidate_manifest_sha256"]
manifest = json.loads(manifest_path.read_text())
for section in ("task_files", "dependencies"):
    for entry in manifest[section].values():
        assert sha(entry["snapshot"]) == entry["sha256"]
test = json.loads((pending.parent / "code-test-evidence.json").read_text())
assert test["returncode"] == 0 and "Ran 5 tests" in test["stderr"] and "\nOK\n" in test["stderr"]
assert test["candidate_manifest_sha256"] == sha(manifest_path)
proof = {"validated": True, "parser": "JSON parser for JSON subset of YAML 1.2 Front Matter", "pending_path": str(pending), "sha256": sha(pending), "stage": expected["stage"], "round": expected["round"], "candidate": data["candidate"], "handoff_sha256": sha(handoff), "time": now()}
Path(str(pending) + ".validation.json").write_text(json.dumps(proof, indent=2))
print(json.dumps(proof))
