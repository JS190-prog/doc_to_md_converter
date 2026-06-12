"""
XY-Cut algorithm for document layout reading order detection.

Based on the recursive projection-based segmentation approach described in:
"XYLayoutLM: Towards Layout-Aware Multimodal Networks For Visually-Rich
Document Understanding" (arXiv:2203.06947)
"""

import numpy as np


def recursive_xy_cut(boxes, indices, res):
    """
    Recursively split bounding boxes via X/Y projections to determine
    reading order.

    Args:
        boxes:   np.ndarray of shape [N, 4] with columns [x0, y0, x1, y1].
        indices: np.ndarray of indices into *boxes* that remain to be sorted.
        res:     list – sorted indices are **appended** in reading order.
    """
    if len(indices) == 0:
        return

    if len(indices) == 1:
        res.append(indices[0])
        return

    cur_boxes = boxes[indices]

    # --- Y-axis projection (horizontal cut) ---
    y_min = int(cur_boxes[:, 1].min())
    y_max = int(cur_boxes[:, 3].max())
    if y_max <= y_min:
        # Degenerate: all boxes on the same row – sort left-to-right
        order = np.argsort(cur_boxes[:, 0])
        for idx in order:
            res.append(indices[idx])
        return

    y_proj = np.zeros(y_max - y_min, dtype=int)
    for b in cur_boxes:
        y0 = max(0, int(b[1]) - y_min)
        y1 = min(len(y_proj), int(b[3]) - y_min)
        y_proj[y0:y1] += 1

    y_splits = _find_splits(y_proj)

    if len(y_splits) == 0:
        # Cannot split on Y – try X
        _x_cut(boxes, indices, cur_boxes, res)
        return

    # Split into horizontal bands
    bands = _split_by_ranges(cur_boxes, indices, y_splits, y_min, axis="y")

    for band_indices in bands:
        if len(band_indices) == 1:
            res.append(band_indices[0])
        else:
            # Try X-cut within each band
            _x_cut(boxes, band_indices, boxes[band_indices], res)


def _x_cut(boxes, indices, cur_boxes, res):
    """Attempt to split *indices* by X-axis projection."""
    x_min = int(cur_boxes[:, 0].min())
    x_max = int(cur_boxes[:, 2].max())
    if x_max <= x_min:
        order = np.argsort(cur_boxes[:, 1])
        for idx in order:
            res.append(indices[idx])
        return

    x_proj = np.zeros(x_max - x_min, dtype=int)
    for b in cur_boxes:
        x0 = max(0, int(b[0]) - x_min)
        x1 = min(len(x_proj), int(b[2]) - x_min)
        x_proj[x0:x1] += 1

    x_splits = _find_splits(x_proj)

    if len(x_splits) == 0:
        # Cannot split further – output in top-to-bottom, left-to-right order
        order = np.lexsort((cur_boxes[:, 0], cur_boxes[:, 1]))
        for idx in order:
            res.append(indices[idx])
        return

    columns = _split_by_ranges(cur_boxes, indices, x_splits, x_min, axis="x")

    for col_indices in columns:
        if len(col_indices) == 1:
            res.append(col_indices[0])
        else:
            recursive_xy_cut(boxes, np.array(col_indices), res)


def _find_splits(projection):
    """
    Find gap positions in a 1-D projection histogram.
    Returns a list of (start, end) ranges of non-zero regions.
    """
    is_nonzero = projection > 0
    if not np.any(is_nonzero):
        return []

    diff = np.diff(is_nonzero.astype(int))
    starts = np.where(diff == 1)[0] + 1
    ends = np.where(diff == -1)[0] + 1

    # Handle edge cases
    if is_nonzero[0]:
        starts = np.concatenate([[0], starts])
    if is_nonzero[-1]:
        ends = np.concatenate([ends, [len(projection)]])

    if len(starts) <= 1:
        return []

    return list(zip(starts, ends))


def _split_by_ranges(cur_boxes, indices, ranges, offset, axis):
    """
    Assign each box index to the range it belongs to.
    axis: "y" uses columns 1,3;  "x" uses columns 0,2.
    """
    if axis == "y":
        centers = (cur_boxes[:, 1] + cur_boxes[:, 3]) / 2.0 - offset
    else:
        centers = (cur_boxes[:, 0] + cur_boxes[:, 2]) / 2.0 - offset

    groups = [[] for _ in ranges]
    for i, c in enumerate(centers):
        best = 0
        best_dist = abs(c - (ranges[0][0] + ranges[0][1]) / 2.0)
        for j, (s, e) in enumerate(ranges):
            d = abs(c - (s + e) / 2.0)
            if d < best_dist:
                best_dist = d
                best = j
        groups[best].append(indices[i])

    return [g for g in groups if g]
