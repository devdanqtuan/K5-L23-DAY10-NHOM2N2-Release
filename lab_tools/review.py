#!/usr/bin/env python3
"""Make a local HTML review queue and an unfilled CSV for the reviewers."""
import argparse
import csv
from html import escape
import os
from pathlib import Path
from urllib.parse import quote
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validator"))
from validate import Delivery, read_json


def overlay(bounds, color):
    x, y, right, bottom = bounds
    return (f'<rect x="{x}" y="{y}" width="{right-x}" height="{bottom-y}" '
            f'fill="none" stroke="{color}" stroke-width="2" />')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--rules", type=Path)
    args = parser.parse_args()
    delivery = Delivery(args.delivery)
    candidates = read_json(args.candidates)["candidates"]
    dimensions = {Path(row["file_name"]).stem: (row["width"], row["height"])
                  for row in read_json(delivery.path("panoptic.json"))["images"]}
    checks = {}
    for candidate in candidates:
        checks.setdefault(candidate["image"], set()).update(candidate["possible_types"])
    args.log.parent.mkdir(parents=True, exist_ok=True)
    if not args.log.exists():
        with args.log.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("image", "type", "verdict", "note"))
            for image, types in checks.items():
                swaps = {"class_swap", "category_swap"}
                for kind in sorted(types - swaps):
                    writer.writerow((image, kind, "", ""))
                if types & swaps:
                    writer.writerow((image, "", "", ""))
    hashes = []
    if args.rules:
        hashes = sorted({row["target"] for row in read_json(args.rules)["errors"]
                         if row["type"] == "wrong_hash"})
        hash_log = args.log.with_name("hash_review.csv")
        if hashes and not hash_log.exists():
            with hash_log.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("image", "verdict", "note"))
                writer.writerows((name, "", "") for name in hashes)

    def link(name, key):
        source = delivery.path(delivery.items[name][key])
        return escape(quote(Path(os.path.relpath(source, args.html.parent)).as_posix()), quote=True)

    args.html.parent.mkdir(parents=True, exist_ok=True)
    with args.html.open("w", encoding="utf-8") as page:
        page.write("""<!doctype html><html lang="vi"><meta charset="utf-8">
<title>Review nhãn COCO</title><style>
body{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#192a38}
article{border-top:1px solid #aaa;padding:1rem 0}svg{display:block;width:min(100%,850px);height:auto}
</style><h1>Review nhãn COCO</h1>
<p>Khung cam là bbox segment panoptic, khung xanh là bbox detection.
Mở ảnh gốc và mask để xem vật. Ghi tên người xem và điều quan sát được vào cột note.
Với lệch lớp, chọn class_swap nếu detection sai, category_swap nếu panoptic sai.</p>
""")
        if hashes:
            page.write("<h2>Ảnh sai hash</h2><p>Mở từng ảnh để kiểm rồi điền hash_review.csv.</p><ul>")
            for name in hashes:
                page.write(f'<li><a href="{link(name, "image")}">{escape(name)}</a></li>')
            page.write("</ul>")
        for index, candidate in enumerate(candidates, 1):
            name = candidate["image"]
            image, mask = link(name, "image"), link(name, "mask")
            width, height = dimensions[name]
            segment = candidate["segment"]
            types = escape(" / ".join(candidate["possible_types"]))
            page.write(f'<article><h2>{escape(name)} · {types}</h2>'
                       f'<p>Ứng viên {index}/{len(candidates)} · Segment {segment["id"]} '
                       f'({escape(segment["class"])}, {segment["pixels"]} px)</p>'
                       f'<p><a href="{image}">Ảnh gốc</a> · <a href="{mask}">Mask panoptic</a></p>')
            for box in candidate["boxes"]:
                page.write(f'<p>Detection dòng {box["line"]} · {escape(box["class"])} · '
                           f'IoU {box["iou"]} · Tỉ lệ pixel mask trong box {box["mask_coverage"]}</p>')
            page.write(f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
                       f'<image href="{image}" width="{width}" height="{height}"/>'
                       + overlay(segment["bounds"], "#ff7700"))
            for box in candidate["boxes"]:
                page.write(overlay(box["bounds"], "#00e5ff"))
            page.write("</svg></article>\n")
        page.write("</html>\n")
    print(f"{len(candidates)} ứng viên trên {len(checks)} ảnh → {args.html}")


if __name__ == "__main__":
    main()
