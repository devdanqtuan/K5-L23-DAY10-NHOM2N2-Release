#!/usr/bin/env python3
"""Build the detection v2 handover after the group has reviewed the delivery."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / name) for name in ("validator", "scripts")]
from validate import Delivery, read_csv, read_json, sha256, write_json
import lineage
from metrics import SEMANTIC_TYPES, RULE_TYPES
from pack_release import build_zip

REWORK = {"missing_image", "invalid_class", "bbox_out_of_bounds", "duplicate_box",
          "class_swap", "bbox_drift", "missing_box"}
PANOPTIC = {"invalid_category_id", "thing_overlap", "category_swap", "instance_merge"}


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)


def findings(run, delivery, *, require_complete=True):
    rules = {(row["type"], row["target"]) for row in read_json(run / "rules.json")["errors"]}
    if any(kind not in RULE_TYPES for kind, _ in rules):
        raise ValueError("rules.json chứa loại lỗi ngoài danh sách lỗi luật.")
    candidates = defaultdict(set)
    for row in read_json(run / "candidates.json")["candidates"]:
        candidates[row["image"]].update(row["possible_types"])
    reviewed = defaultdict(set)
    for row in read_csv(run / "review_log.csv"):
        name, kind, verdict, note = (row[key].strip() for key in ("image", "type", "verdict", "note"))
        if not require_complete and not verdict:
            continue
        if (name not in delivery.items or kind not in SEMANTIC_TYPES
                or verdict not in {"confirmed", "rejected"} or len(note) < 20):
            raise ValueError(f"Review chưa hoàn chỉnh: {name}. Cần loại, kết luận và ghi chú từ 20 ký tự.")
        reviewed[name].add(kind)
        if verdict == "confirmed":
            rules.add((kind, name))
    missing = [name for name, types in candidates.items()
               if not review_covers(types, reviewed[name])]
    if require_complete and missing:
        raise ValueError(f"Chưa chốt review cho {len(missing)} ảnh: {', '.join(sorted(missing)[:8])}")
    return rules


def review_covers(types, reviewed):
    swaps = {"class_swap", "category_swap"}
    return (types - swaps <= reviewed
            and (not (types & swaps) or bool(reviewed & swaps)))


def check_hash_review(run, errors):
    expected = {name for kind, name in errors if kind == "wrong_hash"}
    if not expected:
        return set()
    reviewed = {}
    for row in read_csv(run / "hash_review.csv"):
        name, verdict, note = (row[key].strip() for key in ("image", "verdict", "note"))
        if name not in expected or name in reviewed or verdict not in {"intact", "damaged"} or not note:
            raise ValueError(f"Dòng hash_review.csv chưa hợp lệ: {name}")
        reviewed[name] = verdict
    if expected != set(reviewed):
        raise ValueError(f"Cần mở kiểm các ảnh wrong_hash: {sorted(expected - set(reviewed))}")
    return {name for name in reviewed if reviewed[name] == "damaged"}


def build(folder, delivery, rid, errors, damaged):
    splits = defaultdict(Counter)
    guidelines = defaultdict(set)
    reasons = defaultdict(list)
    for kind, name in sorted(errors):
        reasons[name].append(kind)
    for meta in delivery.meta.values():
        splits[meta["scene_id"]][meta["split"]] += 1
    split_map = {}
    for scene, counts in splits.items():
        ranking = counts.most_common()
        if len(ranking) > 1 and ranking[0][1] == ranking[1][1]:
            raise ValueError(f"Cảnh {scene} hòa số ảnh giữa các split. Nhóm cần xác định split.")
        split_map[scene] = ranking[0][0]
    for sub in ("images", "labels"):
        (folder / sub).mkdir(parents=True)
    manifest, trace, rework, counts = [], [], [], Counter()
    for name, item in sorted(delivery.items.items()):
        meta = delivery.meta[name]
        job = delivery.jobs[meta["job_id"]]
        rejected = [kind for kind in reasons[name] if kind in REWORK or (kind == "wrong_hash" and name in damaged)]
        if rejected:
            rework.extend((name, kind, job["annotator"], job["reviewer"], "Khôi phục ảnh hoặc gán lại; kiểm lại trước khi nhập lô")
                          for kind in rejected)
            continue
        for key, sub in (("image", "images"), ("label", "labels")):
            source = delivery.path(item[key])
            destination = folder / sub / source.name
            shutil.copyfile(source, destination)
            manifest.append((destination.relative_to(folder).as_posix(), sha256(destination)))
        for line in delivery.path(item["label"]).read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[delivery.classes[int(line.split()[0])]] += 1
        trace.append((name, meta["scene_id"], split_map[meta["scene_id"]], meta["job_id"],
                      job["annotator"], job["reviewer"], job["guideline"]))
        guidelines[job["guideline"]].add(meta["job_id"])
    write_csv(folder / "manifest.csv", ("file", "sha256"), sorted(manifest))
    write_csv(folder / "label_summary.csv", ("class", "count"), [*sorted(counts.items()), ("TOTAL", sum(counts.values()))])
    write_csv(folder / "truyvet.csv", ("image", "scene_id", "split", "job_id", "annotator", "reviewer", "guideline"), trace)
    write_csv(folder / "rework_queue.csv", ("image", "type", "annotator", "reviewer", "action"), rework)
    count = len({name for _, name in errors})
    rate = count / len(delivery.items)
    decision = "Hold" if rate > 0.02 else "Release"
    text = "\n".join([
        f"Release: {rid}_v2", f"Parent: {rid}", f"Số ảnh: {len(trace)}", f"Số nhãn: {sum(counts.values())}",
        "Guideline: " + ", ".join(f"{version} ({', '.join(sorted(jobs))})" for version, jobs in sorted(guidelines.items())),
        f"QC v1: {count}/{len(delivery.items)} = {rate:.1%}",
        f"Kết luận v1: {decision} — tỷ lệ lỗi {rate:.1%} với ngưỡng 2%",
        f"Kết luận v2: Release — lô detection, tách {len({row[0] for row in rework})} ảnh cần rework",
        "Ghi chú: split lấy đa số trong cảnh, guideline theo job. Hash v2 tính lại từ bytes; ảnh sai hash đã được mở kiểm theo hash_review.csv.",
        "Rework giao cho người gán và người kiểm theo rework_queue.csv.",
        "Báo team panoptic kiểm lại: " + (", ".join(f"{name} ({kind})" for kind, name in sorted(errors) if kind in PANOPTIC) or "không có ảnh được xác nhận."),
        "",
    ])
    (folder / "README.txt").write_text(text, encoding="utf-8")
    return decision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run
    delivery = Delivery(run / "delivery")
    rid = read_json(delivery.path("release.json"))["release_id"]
    errors = findings(run, delivery)
    damaged = check_hash_review(run, errors)
    handover = run / "handover"
    handover.mkdir(exist_ok=True)
    target = handover / f"{rid}_v2"
    with TemporaryDirectory(dir=handover) as tmp:
        folder = Path(tmp) / target.name
        decision = build(folder, delivery, rid, errors, damaged)
        data = build_zip(folder)
        if target.exists():
            if build_zip(target) != data:
                raise SystemExit(f"{target} đã có nội dung khác. Chuyển bản hiện có sang chỗ lưu riêng trước.")
        else:
            folder.rename(target)
    zip_path = target.with_suffix(".zip")
    zip_path.write_bytes(data)
    target.with_suffix(".sha256").write_text(f"{hashlib.sha256(data).hexdigest()}  {zip_path.name}\n", encoding="utf-8")
    write_json(run / "errors.json", {"errors": [{"type": kind, "target": name} for kind, name in sorted(errors)]})
    events = lineage.read(run.parent)
    for event in ({"event": "decision", "release_id": rid, "decision": decision.upper()},
                  {"event": "release", "release_id": target.name, "parent": rid}):
        if event not in events:
            lineage.append(run.parent, event)
    print(f"{decision} {rid} → {target}")


if __name__ == "__main__":
    main()
