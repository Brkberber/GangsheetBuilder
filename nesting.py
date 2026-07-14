# ============================================================
# nesting.py — Shape-aware (silhouette) bin-packing
# ============================================================
#
# Unlike the rectangular MaxRects packer, this one packs by the
# design's actual shape (its alpha silhouette), not its bounding
# box. That lets non-rectangular designs interlock:
#
#   Two 12"-wide T-shapes placed as bounding boxes need 24" and
#   won't fit on a 22" roll. But flip one 180° and the wide bar
#   of one tucks beside the narrow stem of the other -> the pair
#   fits in ~22". Round designs likewise nest into each other's
#   corners instead of wasting a full square each.
#
# How it works:
#   * Each design's alpha channel is downsampled to a coarse
#     boolean grid (one cell ~= GRID_PX pixels).
#   * The grid mask is dilated by the border amount so every
#     design keeps its 0.2" clearance from its neighbours.
#   * Designs are placed one by one (largest first). For each we
#     try all four 90-degree orientations and, via a fast
#     correlation (cv2.matchTemplate), find the lowest / leftmost
#     collision-free spot on the current sheet. Overflows spill
#     onto a new page.
#
# Coarse-grid rounding never causes overlap because the dilation
# (0.2") is larger than one grid cell, so neighbours always keep
# a real gap.
# ============================================================

import numpy as np
import cv2
from PIL import Image

GRID_PX = 30          # grid cell size in pixels (0.1" at 300 DPI)
_ALPHA_THRESHOLD = 10  # alpha above this counts as "solid"


def _downsample_mask(alpha: np.ndarray, grid: int) -> np.ndarray:
    """Block-max downsample an alpha array to a boolean grid mask."""
    h, w = alpha.shape
    gh = -(-h // grid)   # ceil division
    gw = -(-w // grid)
    padded = np.zeros((gh * grid, gw * grid), dtype=alpha.dtype)
    padded[:h, :w] = alpha
    block = padded.reshape(gh, grid, gw, grid).max(axis=(1, 3))
    return (block > _ALPHA_THRESHOLD).astype(np.float32)


def _dilate(mask: np.ndarray, d: int) -> np.ndarray:
    """Pad by d cells on every side, then grow the shape by d cells."""
    mh, mw = mask.shape
    canvas = np.zeros((mh + 2 * d, mw + 2 * d), dtype=np.float32)
    canvas[d:d + mh, d:d + mw] = mask
    if d > 0:
        kernel = np.ones((2 * d + 1, 2 * d + 1), dtype=np.uint8)
        canvas = cv2.dilate(canvas, kernel)
    return canvas


def _orient_image(img: Image.Image, k: int) -> Image.Image:
    """Rotate a PIL image by k * 90 degrees CCW (matches np.rot90)."""
    if k == 0:
        return img
    if k == 1:
        return img.transpose(Image.Transpose.ROTATE_90)
    if k == 2:
        return img.transpose(Image.Transpose.ROTATE_180)
    return img.transpose(Image.Transpose.ROTATE_270)


def _prepare(items, grid, d):
    """Precompute per-design orientation masks (deduped)."""
    prepared = []
    for it in items:
        base_alpha = np.asarray(it['image'].getchannel('A'))
        orientations = []
        seen = set()
        for k in (0, 1, 2, 3):
            a = np.rot90(base_alpha, k)
            md = _dilate(_downsample_mask(a, grid), d)
            key = (md.shape, md.tobytes())
            if key in seen:            # symmetric orientation -> skip
                continue
            seen.add(key)
            orientations.append({
                'k': k,
                'md': md,
                'mh': md.shape[0],
                'mw': md.shape[1],
            })
        prepared.append({
            'item': it,
            'oris': orientations,
            'area': base_alpha.shape[0] * base_alpha.shape[1],
        })
    # Largest area first packs more reliably.
    prepared.sort(key=lambda p: p['area'], reverse=True)
    return prepared


def _find_spot(occ, top, o, cols, max_rows):
    """Lowest-then-leftmost collision-free grid position for one orientation."""
    mh, mw = o['mh'], o['mw']
    if mw > cols:
        return None
    need = top + mh
    if occ.shape[0] < need:
        occ = np.vstack([occ,
                         np.zeros((need - occ.shape[0], cols), dtype=np.float32)])
    res = cv2.matchTemplate(occ, o['md'], cv2.TM_CCORR)
    feasible = np.argwhere(res < 0.5)          # row-major -> already bottom-left
    for gy, gx in feasible:
        if gy + mh <= max_rows:
            return int(gy), int(gx), occ
    return None


def pack_shapes(items, gang_width, max_height, padding_px, grid=GRID_PX):
    """
    Shape-aware packer. Same contract as packing.pack_images.

    items: list of dicts with keys 'image' (RGBA PIL, cropped to content),
           'w', 'h' (content pixels — unused here, kept for symmetry).

    Returns (pages, unpacked) where each placement dict has:
        'image' (oriented PIL), 'x', 'y' (paste px), 'cw', 'ch' (px).
    """
    d = max(1, round(padding_px / grid))     # clearance in grid cells
    cols = gang_width // grid
    max_rows = max_height // grid

    prepared = _prepare(items, grid, d)
    pages = []
    remaining = prepared

    while remaining:
        occ = np.zeros((1, cols), dtype=np.float32)
        top = 0
        placed = []
        leftover = []

        for p in remaining:
            best = None      # (gy, gx, orientation)
            for o in p['oris']:
                spot = _find_spot(occ, top, o, cols, max_rows)
                if spot is None:
                    continue
                gy, gx, occ = spot
                if best is None or (gy, gx) < (best[0], best[1]):
                    best = (gy, gx, o)

            if best is None:
                leftover.append(p)
                continue

            gy, gx, o = best
            # ensure occ tall enough, then stamp the dilated mask
            need = gy + o['mh']
            if occ.shape[0] < need:
                occ = np.vstack([occ,
                                 np.zeros((need - occ.shape[0], cols),
                                          dtype=np.float32)])
            occ[gy:gy + o['mh'], gx:gx + o['mw']] = np.maximum(
                occ[gy:gy + o['mh'], gx:gx + o['mw']], o['md'])
            top = max(top, gy + o['mh'])

            placed.append({
                'item': p['item'],
                'k': o['k'],
                'px': (gx + d) * grid,   # content top-left (skip dilation halo)
                'py': (gy + d) * grid,
            })

        if not placed:
            return _finalize(pages), [p['item'] for p in leftover]

        pages.append(placed)
        remaining = leftover

    return _finalize(pages), []


def _finalize(pages):
    """Materialise oriented images for rendering."""
    out_pages = []
    for page in pages:
        out = []
        for pl in page:
            img = _orient_image(pl['item']['image'], pl['k'])
            out.append({
                'image': img,
                'x': pl['px'],
                'y': pl['py'],
                'cw': img.width,
                'ch': img.height,
            })
        out_pages.append(out)
    return out_pages
