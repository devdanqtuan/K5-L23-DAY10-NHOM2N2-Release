"""Focused regression tests for candidate geometry on independent synthetic masks."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validator"))
from validate import Box, cross_check


class CandidateGeometryTest(unittest.TestCase):
    def test_translation_with_high_mask_coverage_still_goes_to_review(self):
        segment = {"id": 1, "name": "person", "bbox": [20, 20, 100, 40]}
        mask = [(20, 20, 120), *((y, 24, 104) for y in range(21, 60))]
        box = Box("person", (28, 20, 128, 60), (100, 40), 1)
        result = cross_check([box], [segment], {1: mask}, 200 * 100)
        self.assertEqual([row["possible_types"] for row in result], [["bbox_drift"]])

    def test_box_for_neighbor_does_not_hide_missing_instance(self):
        segments = [
            {"id": 1, "name": "person", "bbox": [0, 0, 60, 60]},
            {"id": 2, "name": "person", "bbox": [40, 0, 60, 60]},
        ]
        runs = {
            1: [(0, 0, 40), *((y, 0, 60) for y in range(1, 60))],
            2: [(0, 40, 100), *((y, 60, 100) for y in range(1, 60))],
        }
        box = Box("person", (0, 0, 60, 60), (60, 60), 1)
        result = cross_check([box], segments, runs, 200 * 100)
        self.assertEqual([row["possible_types"] for row in result], [["missing_box"]])
        self.assertEqual(result[0]["segment"]["id"], 2)

    def test_heavily_covered_neighbor_is_not_flagged(self):
        segments = [
            {"id": 1, "name": "person", "bbox": [0, 0, 100, 80]},
            {"id": 2, "name": "person", "bbox": [0, 0, 50, 50]},
        ]
        runs = {
            1: [*((y, 50, 100) for y in range(50)), *((y, 0, 100) for y in range(50, 80))],
            2: [(y, 0, 50) for y in range(50)],
        }
        box = Box("person", (0, 0, 100, 80), (100, 80), 1)
        self.assertEqual(cross_check([box], segments, runs, 200 * 100), [])

    def test_two_overlapping_boxes_can_explain_one_merged_segment(self):
        segment = {"id": 1, "name": "person", "bbox": [0, 0, 120, 60]}
        mask = [(y, 0, 120) for y in range(60)]
        boxes = [
            Box("person", (0, 0, 85, 60), (85, 60), 1),
            Box("person", (35, 0, 120, 60), (85, 60), 2),
        ]
        result = cross_check(boxes, [segment], {1: mask}, 200 * 100)
        self.assertEqual([row["possible_types"] for row in result], [["instance_merge"]])

    def test_shifted_box_with_low_iou_is_not_silently_suppressed(self):
        segment = {"id": 1, "name": "person", "bbox": [0, 0, 100, 100]}
        runs = {1: [(y, 0, 100) for y in range(100)]}
        box = Box("person", (45, 45, 145, 145), (100, 100), 1)
        result = cross_check([box], [segment], runs, 250 * 250)
        self.assertEqual([row["possible_types"] for row in result], [["bbox_drift"]])

    def test_small_intersection_with_different_sized_box_is_not_drift(self):
        segment = {"id": 1, "name": "person", "bbox": [0, 0, 100, 100]}
        runs = {1: [(y, 0, 100) for y in range(100)]}
        box = Box("person", (50, 50, 130, 130), (80, 80), 1)
        result = cross_check([box], [segment], runs, 250 * 250)
        self.assertFalse(any("bbox_drift" in row["possible_types"] for row in result))
