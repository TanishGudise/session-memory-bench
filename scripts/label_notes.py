"""Hand-labelling of distilled notes (PREREGISTRATION section 5). Writes notes_labels.json pre-filled with the
pattern labels as suggestions and "reviewed": false, and prints every note with its suggestion. Edit the labels
by hand against the lesson definitions in lessons.yaml, then set "reviewed": true and "labeled_by"; freeze-corpus
refuses notes that aren't reviewed.

  python scripts/label_notes.py <corpus>
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    corpus = ROOT / "runs" / "history" / sys.argv[1]
    notes = [json.loads(l) for l in (corpus / "notes.jsonl").read_text().splitlines() if l.strip()]
    out = corpus / "notes_labels.json"
    doc = json.loads(out.read_text()) if out.exists() else {"reviewed": False, "labeled_by": "", "labels": {}}
    ids = {n["id"] for n in notes}
    new = [n for n in notes if n["id"] not in doc["labels"]]
    for n in new:  # notes from newly distilled sessions get the pattern labels as suggestions
        doc["labels"][n["id"]] = n["pattern_lessons"]
    doc["labels"] = {k: v for k, v in doc["labels"].items() if k in ids}
    if new:
        doc["reviewed"] = False
    out.write_text(json.dumps(doc, indent=1))
    labels = doc["labels"]
    print(f"{len(new)} new notes to review; reviewed={doc['reviewed']}")
    for n in notes:
        print(f"{n['id']}  [{n['repo']} {n['date']}]  {n['text']}\n    -> {labels.get(n['id'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
