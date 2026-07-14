# ============================================================
# packing.py — MaxRects 2D Bin-Packing with best-of search
# ============================================================
#
# Goal: pack all designs onto a fixed-width roll (gang sheet)
# while MINIMISING the total used length (height).
#
# Why not the old skyline packer?
#   The old code rotated each design greedily to minimise that
#   single design's top edge. A 10.5"-wide-but-tall design got
#   rotated to ~15" wide, so a second copy no longer fit beside
#   it on a 22" sheet -> designs stacked instead of sitting side
#   by side. That greedy, look-ahead-blind rotation both wasted
#   material and broke the obvious "two-up" layout.
#
# This version uses the MaxRects free-rectangle model and runs
# several packing strategies (sort order x rotation x placement
# heuristic), then keeps whichever result uses the least total
# length. The side-by-side layout wins automatically because it
# is genuinely shorter — no special-casing required.
# ============================================================

from PIL import Image


# ── Free-rectangle primitive ─────────────────────────────────

class _Rect:
    __slots__ = ('x', 'y', 'w', 'h')

    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _MaxRectsBin:
    """A single page/sheet modelled as a set of free rectangles."""

    def __init__(self, width, height, allow_rotate):
        self.width = width
        self.height = height
        self.allow_rotate = allow_rotate
        self.free = [_Rect(0, 0, width, height)]

    # -- scoring ------------------------------------------------
    @staticmethod
    def _score(free, w, h, heuristic):
        """Lower score = better fit. Returns None if it doesn't fit."""
        if w > free.w or h > free.h:
            return None
        leftover_h = free.w - w
        leftover_v = free.h - h
        short = min(leftover_h, leftover_v)
        long = max(leftover_h, leftover_v)
        if heuristic == 'bssf':          # Best Short Side Fit
            return (short, long)
        if heuristic == 'baf':           # Best Area Fit
            return (free.w * free.h - w * h, short)
        # 'bl' — Bottom-Left (minimise top edge, then x)
        return (free.y + h, free.x)

    def insert(self, w, h, heuristic):
        """Place a w x h box. Returns (x, y, w, h, rotated) or None."""
        best = None          # (score, x, y, w, h, rotated)

        orientations = [(w, h, False)]
        if self.allow_rotate and w != h:
            orientations.append((h, w, True))

        for free in self.free:
            for tw, th, rot in orientations:
                score = self._score(free, tw, th, heuristic)
                if score is None:
                    continue
                if best is None or score < best[0]:
                    best = (score, free.x, free.y, tw, th, rot)

        if best is None:
            return None

        _, x, y, pw, ph, rot = best
        self._place(x, y, pw, ph)
        return x, y, pw, ph, rot

    # -- free-rect maintenance ----------------------------------
    def _place(self, x, y, w, h):
        placed = _Rect(x, y, w, h)
        new_free = []
        for f in self.free:
            new_free.extend(self._split(f, placed))
        self.free = new_free
        self._prune()

    @staticmethod
    def _split(free, used):
        # No overlap -> free rectangle survives unchanged.
        if (used.x >= free.x + free.w or used.x + used.w <= free.x or
                used.y >= free.y + free.h or used.y + used.h <= free.y):
            return [free]

        result = []
        # Vertical overlap -> carve top and bottom slabs.
        if used.x < free.x + free.w and used.x + used.w > free.x:
            if used.y > free.y and used.y < free.y + free.h:
                result.append(_Rect(free.x, free.y, free.w, used.y - free.y))
            if used.y + used.h < free.y + free.h:
                result.append(_Rect(free.x, used.y + used.h, free.w,
                                    free.y + free.h - (used.y + used.h)))
        # Horizontal overlap -> carve left and right slabs.
        if used.y < free.y + free.h and used.y + used.h > free.y:
            if used.x > free.x and used.x < free.x + free.w:
                result.append(_Rect(free.x, free.y, used.x - free.x, free.h))
            if used.x + used.w < free.x + free.w:
                result.append(_Rect(used.x + used.w, free.y,
                                    free.x + free.w - (used.x + used.w), free.h))
        return result

    def _prune(self):
        """Drop any free rectangle fully contained inside another."""
        keep = []
        n = len(self.free)
        for i in range(n):
            a = self.free[i]
            contained = False
            for j in range(n):
                if i == j:
                    continue
                b = self.free[j]
                if (a.x >= b.x and a.y >= b.y and
                        a.x + a.w <= b.x + b.w and a.y + a.h <= b.y + b.h):
                    # tie-break so two identical rects don't both get dropped
                    if a.w * a.h < b.w * b.h or (a.w * a.h == b.w * b.h and i > j):
                        contained = True
                        break
            if not contained:
                keep.append(a)
        self.free = keep


# ── Single full pack with one fixed strategy ─────────────────

def _pack_once(items, gang_width, max_height, pad, sort_key,
               allow_rotate, heuristic):
    # Box = content plus border on every side.
    order = sorted(items, key=lambda x: sort_key(x), reverse=True)
    pages = []
    remaining = order

    while remaining:
        bin_ = _MaxRectsBin(gang_width, max_height, allow_rotate)
        placed = []
        leftover = []

        for it in remaining:
            bw, bh = it['w'] + 2 * pad, it['h'] + 2 * pad
            res = bin_.insert(bw, bh, heuristic)
            if res is None:
                leftover.append(it)
                continue
            x, y, w, h, rot = res
            placed.append({'item': it, 'x': x, 'y': y,
                           'w': w, 'h': h, 'rotate': rot})

        if not placed:
            # Nothing left fits even on an empty page -> unpackable.
            return pages, leftover

        pages.append(placed)
        remaining = leftover

    return pages, []


def _box_height(pages):
    return sum(max(p['y'] + p['h'] for p in page) for page in pages)


# ── Public entry point ───────────────────────────────────────

# Strategies to try. Each design set is packed with every combo
# and the tightest (shortest total length) result is kept.
_SORTS = [
    lambda x: x['w'] * x['h'],
    lambda x: x['h'],
    lambda x: x['w'],
    lambda x: max(x['w'], x['h']),
]
_HEURISTICS = ('bssf', 'baf', 'bl')


def pack_images(items: list, gang_width: int, max_gang_height: int,
                padding_px: int) -> tuple[list, list]:
    """
    Rectangular packer: pack images onto a fixed-width roll,
    minimising total length. Tries several strategies and keeps
    the tightest result.

    Args:
        items:           list of dicts with keys 'image' (PIL, content),
                         'w', 'h' (content pixels, WITHOUT border)
        gang_width:      sheet width in pixels
        max_gang_height: maximum sheet height in pixels
        padding_px:      border on every side of each design

    Returns:
        (pages, unpacked)
        - pages: list of pages; each is a list of placement dicts with
                 keys: image (oriented), x, y (paste px), cw, ch (px)
        - unpacked: images that couldn't fit on any page
    """
    best = None  # (unpacked_count, num_pages, box_height, pages, unpacked)

    for skey in _SORTS:
        for allow_rotate in (False, True):
            for heuristic in _HEURISTICS:
                pages, unpacked = _pack_once(
                    items, gang_width, max_gang_height, padding_px,
                    skey, allow_rotate, heuristic,
                )
                if not pages:
                    continue
                candidate = (len(unpacked), len(pages),
                             _box_height(pages), pages, unpacked)
                if best is None or candidate[:3] < best[:3]:
                    best = candidate

    if best is None:
        return [], list(items)

    _uc, _np, _th, best_pages, best_unpacked = best

    # Materialise the winning layout: paste content inside the box
    # (offset by the border), rotating images only for the winner.
    final_pages = []
    for page in best_pages:
        out = []
        for p in page:
            img = p['item']['image']
            if p['rotate']:
                img = img.transpose(Image.Transpose.ROTATE_90)
            out.append({
                'image': img,
                'x': p['x'] + padding_px,
                'y': p['y'] + padding_px,
                'cw': img.width,
                'ch': img.height,
            })
        final_pages.append(out)

    return final_pages, best_unpacked
