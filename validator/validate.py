#!/usr/bin/env python3
"""Validate a delivery and generate evidence for human review."""
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations, groupby
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pngutil import read_rgb


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path):
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Delivery:
    def __init__(self, root):
        self.root = root.resolve()
        self.items = read_json(self.path("manifest.json"))["items"]
        self.meta = {row["image"]: row for row in read_json(self.path("metadata.json"))["items"]}
        self.jobs = {row["job_id"]: row for row in read_csv(self.path("jobs.csv"))}
        self.classes = {}
        for line in self.path("classes.txt").read_text(encoding="utf-8").splitlines():
            if line.strip():
                key, name = line.split(maxsplit=1)
                self.classes[int(key)] = name.strip()

    def path(self, name):
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Path outside delivery: {name}")
        return path


@dataclass(frozen=True)
class Box:
    name: str
    bounds: tuple[float, float, float, float]
    size: tuple[float, float]
    line: int


@dataclass(frozen=True)
class Pair:
    s: int
    b: int
    overlap: float
    coverage: float
    same: bool


def detection(path, classes, width, height):
    boxes, errors = [], set()
    if not path.is_file():
        return boxes, {"wrong_hash"}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        try:
            category = int(fields[0])
        except ValueError:
            errors.add("invalid_class")
            continue
        if category not in classes:
            errors.add("invalid_class")
        try:
            x, y, w, h = map(float, fields[1:])
        except ValueError:
            errors.add("bbox_out_of_bounds")
            continue
        bounds = ((x - w / 2) * width, (y - h / 2) * height,
                  (x + w / 2) * width, (y + h / 2) * height)
        # Six-decimal YOLO rounding can put a valid box just beyond the edge.
        if (not all(map(math.isfinite, bounds)) or w <= 0 or h <= 0
                or min(bounds[:2]) < -0.01 or bounds[2] > width + 0.01
                or bounds[3] > height + 0.01):
            errors.add("bbox_out_of_bounds")
            continue
        if category in classes:
            boxes.append(Box(classes[category], bounds, (w * width, h * height), number))
    for a, b in combinations(boxes, 2):
        if (a.name == b.name and all(abs(x - y) <= 0.01 for x, y in zip(a.size, b.size))
                and all(abs(x - y) <= 2.1 for x, y in zip(a.bounds, b.bounds))):
            errors.add("duplicate_box")
            break
    return boxes, errors


def mask_runs(path, tracked):
    width, height, pixels = read_rgb(path)
    # Consecutive pixels form a half-open interval on one scanline.
    runs = defaultdict(list)
    for y in range(height):
        row = pixels[y * width * 3:(y + 1) * width * 3]
        x = 0
        for (r, g, b), group in groupby(zip(row[::3], row[1::3], row[2::3])):
            end = x + sum(1 for _ in group)
            segment_id = r | g << 8 | b << 16
            if segment_id in tracked:
                runs[segment_id].append((y, x, end))
            x = end
    return runs


def area(bounds):
    x, y, right, bottom = bounds
    return max(0, right - x) * max(0, bottom - y)


def iou(a, b):
    intersect = area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))
    union = area(a) + area(b) - intersect
    return intersect / union if union else 0


def mask_pixels(runs, bounds):
    left, top, right, bottom = bounds
    left, right = math.ceil(left - 0.5), math.ceil(right - 0.5)
    return sum(max(0, min(end, right) - max(start, left))
               for y, start, end in runs if top <= y + 0.5 < bottom)


def is_translated(box, segment_bounds, coverage):
    """Separate translation from a change in box size or occlusion."""
    comparisons = []
    for start, end, det_start, det_end in (
        (segment_bounds[0], segment_bounds[2], box.bounds[0], box.bounds[2]),
        (segment_bounds[1], segment_bounds[3], box.bounds[1], box.bounds[3]),
    ):
        length = end - start
        if length <= 0 or not 0.88 <= (det_end - det_start) / length <= 1.14:
            return False
        leading, trailing = det_start - start, det_end - end
        comparisons.append(leading * trailing > 0 and
                           min(abs(leading), abs(trailing)) >= max(3, 0.065 * length))
    return any(comparisons) and coverage < 0.975



def cross_check(boxes, segments, runs, image_area):
    segment_bounds = []
    areas = []
    for segment in segments:
        x, y, w, h = segment["bbox"]
        segment_bounds.append((x, y, x + w, y + h))
        areas.append(sum(end - start for _, start, end in runs[segment["id"]]))

    pairs = []
    for s, segment in enumerate(segments):
        if not areas[s]:
            continue
        for b, box in enumerate(boxes):
            overlap = iou(box.bounds, segment_bounds[s])
            if overlap < 0.03:
                continue
            coverage = mask_pixels(runs[segment["id"]], box.bounds) / areas[s]
            pairs.append(Pair(s, b, overlap, coverage, box.name == segment["name"]))

    candidates = []

    def record(types, s, matches):
        segment = segments[s]
        candidates.append({
            "possible_types": types,
            "segment": {"id": segment["id"], "class": segment["name"],
                        "bounds": segment_bounds[s], "pixels": areas[s]},
            "boxes": [{"line": boxes[p.b].line, "class": boxes[p.b].name,
                       "bounds": boxes[p.b].bounds, "iou": round(p.overlap, 3),
                       "mask_coverage": round(p.coverage, 3)} for p in matches],
        })

    used_segments, used_boxes = set(), set()
    # Flag displaced boxes of nearly unchanged size before a high IoU hides
    # them in the same-class matching pass.
    translated = sorted((p for p in pairs if p.same and p.overlap >= 0.43
                         and areas[p.s] >= 120
                         and is_translated(boxes[p.b], segment_bounds[p.s], p.coverage)),
                        key=lambda p: (p.overlap, p.coverage), reverse=True)
    # Establish strong same-class matches first. A class disagreement is
    # examined only if both objects still need a match.
    strong = sorted((p for p in pairs if p.same and p.overlap >= 0.55 and p.coverage >= 0.94),
                    key=lambda p: (p.overlap, p.coverage), reverse=True)
    translated_pairs = {(p.s, p.b) for p in translated}
    for p in strong:
        if ((p.s, p.b) not in translated_pairs
                and p.s not in used_segments and p.b not in used_boxes):
            used_segments.add(p.s)
            used_boxes.add(p.b)

    for p in translated:
        if p.s not in used_segments and p.b not in used_boxes:
            record(["bbox_drift"], p.s, [p])
            used_segments.add(p.s)
            used_boxes.add(p.b)

    for s, segment in enumerate(segments):
        if s in used_segments:
            continue
        options = [p for p in pairs if p.s == s and p.same and p.coverage >= 0.17
                   and p.overlap >= 0.10 and p.b not in used_boxes]
        for first, second in combinations(options, 2):
            a, b = boxes[first.b].bounds, boxes[second.b].bounds
            shared = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
            common = mask_pixels(runs[segment["id"]], shared) / areas[s]
            overlap = iou(a, b)
            exclusive = min(first.coverage, second.coverage) - common
            combined = first.coverage + second.coverage - common
            # Overlapping boxes need stronger independent mask support.
            clean_split = overlap <= 0.30 and exclusive >= 0.12 and combined >= 0.78
            overlapping_split = overlap <= 0.55 and exclusive >= 0.18 and combined >= 0.90
            if clean_split or overlapping_split:
                record(["instance_merge"], s, [first, second])
                used_segments.add(s)
                used_boxes.update((first.b, second.b))
                break

    aligned = sorted((p for p in pairs if not p.same and p.overlap >= 0.62 and p.coverage >= 0.85),
                     key=lambda p: (p.overlap, p.coverage), reverse=True)
    for p in aligned:
        if p.s in used_segments or p.b in used_boxes:
            continue
        record(["class_swap", "category_swap"], p.s, [p])
        used_segments.add(p.s)
        used_boxes.add(p.b)

    shifted = sorted(
        (p for p in pairs if p.same and
         (p.overlap >= 0.23 or
          (p.overlap >= 0.16 and p.coverage >= 0.14
           and is_translated(boxes[p.b], segment_bounds[p.s], p.coverage)))),
        key=lambda p: (p.overlap, p.coverage), reverse=True,
    )
    for p in shifted:
        if p.s in used_segments or p.b in used_boxes:
            continue
        segment_size = area(segment_bounds[p.s])
        size_ratio = area(boxes[p.b].bounds) / segment_size
        if p.coverage < 0.91 and 0.65 <= size_ratio <= 1.8 and areas[p.s] >= 100:
            record(["bbox_drift"], p.s, [p])
        used_segments.add(p.s)
        used_boxes.add(p.b)

    for s, size in enumerate(areas):
        if s in used_segments or size < max(140, 0.0015 * image_area):
            continue
        nearby = [p for p in pairs if p.s == s and
                  ((p.b not in used_boxes and p.same and
                    (p.overlap >= 0.14 or p.coverage >= 0.48))
                   or (p.same and (p.overlap >= 0.58 or p.coverage >= 0.78))
                   or (p.overlap >= 0.40 and p.coverage >= 0.65))]
        if not nearby:
            # A box already committed to a neighbor is weak evidence that
            # this separate segment is annotated. Show that box for review.
            neighbors = sorted((p for p in pairs if p.s == s and p.same),
                               key=lambda p: (p.overlap, p.coverage), reverse=True)
            record(["missing_box"], s, neighbors[:1])
    return candidates


def validate(delivery, generate_candidates):
    panoptic = read_json(delivery.path("panoptic.json"))
    categories = {row["id"]: row for row in panoptic["categories"]}
    images = {Path(row["file_name"]).stem: row for row in panoptic["images"]}
    annotations = {row["image_id"]: row["segments_info"] for row in panoptic["annotations"]}
    errors, candidates = set(), []
    splits = defaultdict(set)
    for name, item in sorted(delivery.items.items()):
        meta = delivery.meta[name]
        splits[meta["scene_id"]].add(meta["split"])
        reasons = set()
        if meta["guideline_version"] != delivery.jobs[meta["job_id"]]["guideline"]:
            reasons.add("guideline_mismatch")
        untrusted = set()
        for file_type in ("image", "label", "mask"):
            path = delivery.path(item[file_type])
            if not path.is_file() and file_type == "image":
                reasons.add("missing_image")
            elif not path.is_file() or sha256(path) != item[f"{file_type}_sha256"]:
                reasons.add("wrong_hash")
                untrusted.add(file_type)
        image = images[name]
        width, height = image["width"], image["height"]
        boxes, box_errors = detection(delivery.path(item["label"]), delivery.classes, width, height)
        reasons.update(box_errors)
        things = []
        for segment in annotations.get(image["id"], []):
            category = categories.get(segment["category_id"])
            if category is None:
                reasons.add("invalid_category_id")
            elif category["isthing"] and segment["id"]:
                things.append({**segment, "name": category["name"]})
        mask_path = delivery.path(item["mask"])
        if "mask" in untrusted:
            runs = {}
        else:
            runs = mask_runs(mask_path, {s["id"] for s in things})
            for segment in things:
                pixels = sum(end - start for _, start, end in runs[segment["id"]])
                if pixels < segment["area"]:
                    reasons.add("thing_overlap")
        if generate_candidates and not reasons:
            individual_things = [segment for segment in things if not segment.get("iscrowd")]
            for candidate in cross_check(boxes, individual_things, runs, width * height):
                candidates.append({"image": name, **candidate})
        errors.update((reason, name) for reason in reasons)
    errors.update(("scene_leak", scene) for scene, values in splits.items() if len(values) > 1)
    return [{"type": kind, "target": name} for kind, name in sorted(errors)], candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--candidates", type=Path)
    args = parser.parse_args()
    outputs = [path.resolve() for path in (args.out, args.candidates) if path]
    if len(set(outputs)) != len(outputs) or any(path.is_relative_to(args.delivery.resolve()) for path in outputs):
        parser.error("Ghi kết quả ra các đường dẫn riêng bên ngoài delivery.")
    errors, candidates = validate(Delivery(args.delivery), args.candidates is not None)
    write_json(args.out, {"errors": errors})
    if args.candidates:
        write_json(args.candidates, {"candidates": candidates})
    print(f"{len(errors)} lỗi luật, {len(candidates)} ứng viên cần xem ảnh.")


if __name__ == "__main__":
    main()
