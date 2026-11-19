#!/usr/bin/env python3
"""Trace the ticket using detection labels and job guideline versions."""
import argparse
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validator"))
from validate import Delivery, write_json


def trace(delivery):
    ticket = delivery.path("incoming/ticket.md").read_text(encoding="utf-8")
    changelog = delivery.path("guideline/changelog.md").read_text(encoding="utf-8")
    affected_classes = set(re.findall(r"Lớp\s+`([^`]+)`", changelog, flags=re.IGNORECASE))
    classes = {str(key) for key, name in delivery.classes.items()
               if name in affected_classes and name in ticket}
    prior = re.search(r"\((v\d+(?:\.\d+)*)\s+cho phép", changelog)
    reported = {row["scene_id"] for row in delivery.meta.values()
                if re.search(rf"(?<!\w){re.escape(row['scene_id'])}(?!\w)", ticket)}
    if not classes or not prior or not reported:
        raise ValueError("Không đọc được lớp, guideline cũ hoặc cảnh từ ticket/changelog.")
    a, b, people = [], [], set()
    for name, item in sorted(delivery.items.items()):
        meta = delivery.meta[name]
        job = delivery.jobs[meta["job_id"]]
        if job["guideline"] != prior[1]:
            continue
        lines = delivery.path(item["label"]).read_text(encoding="utf-8").splitlines()
        if any(line.split()[0] in classes for line in lines if line.strip()):
            (a if meta["scene_id"] in reported else b).append(name)
            people.update((job["annotator"], job["reviewer"]))
    return {"tier_a": a, "tier_b": b, "notify": sorted(people)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = trace(Delivery(args.delivery))
    write_json(args.out, result)
    print(", ".join(f"{key}: {len(values)}" for key, values in result.items()))
