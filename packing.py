# ============================================================
# packing.py — Custom 2D Skyline Bin-Packing Algorithm
# ============================================================
#
# Algorithm: Skyline Bottom-Left with rotation support.
# Places each image at the position that minimizes wasted
# vertical space. Tries both normal and 90° rotated orientations.
# Overflows to new pages when the sheet height is exceeded.
# ============================================================

from PIL import Image


def _find_best_position(skyline: list, img_w: int, img_h: int,
                         gang_width: int, max_height: int):
    """
    Scans the skyline to find the best (x, y) position for an image.
    Also tries rotating the image 90° for a potentially better fit.

    Returns: (best_x, best_y, best_w, best_h, rotate_needed)
    or None if the image doesn't fit on the current page.
    """
    best_y = float('inf')
    best_x = 0
    best_w, best_h = img_w, img_h
    best_skyline_idx = -1
    rotate_needed = False

    for i, (x_pos, seg_w, seg_y) in enumerate(skyline):
        for (try_w, try_h, try_rotate) in [(img_w, img_h, False), (img_h, img_w, True)]:
            if x_pos + try_w > gang_width:
                continue

            max_y = 0
            w_left = try_w
            curr_idx = i
            while w_left > 0 and curr_idx < len(skyline):
                max_y = max(max_y, skyline[curr_idx][2])
                w_left -= skyline[curr_idx][1]
                curr_idx += 1

            if w_left <= 0 and (max_y + try_h <= max_height):
                if max_y + try_h < best_y:
                    best_y = max_y + try_h
                    best_skyline_idx = i
                    best_x = x_pos
                    best_w, best_h = try_w, try_h
                    rotate_needed = try_rotate

    if best_skyline_idx == -1:
        return None

    return best_x, best_y - best_h, best_w, best_h, rotate_needed


def _update_skyline(skyline: list, place_x: int, place_y: int,
                    place_w: int, place_h: int) -> list:
    """
    Updates the skyline after placing an image.
    Merges adjacent nodes with the same height for efficiency.
    """
    new_node = [place_x, place_w, place_y + place_h]
    new_skyline = []

    for node in skyline:
        node_x, node_w, node_y = node
        if node_x >= place_x + place_w or node_x + node_w <= place_x:
            new_skyline.append(node)
        else:
            if node_x < place_x:
                new_skyline.append([node_x, place_x - node_x, node_y])
            if node_x + node_w > place_x + place_w:
                new_skyline.append([place_x + place_w,
                                    (node_x + node_w) - (place_x + place_w),
                                    node_y])

    new_skyline.append(new_node)
    new_skyline.sort(key=lambda n: n[0])

    # Merge adjacent nodes with same height
    merged = []
    for node in new_skyline:
        if merged and merged[-1][0] + merged[-1][1] == node[0] and merged[-1][2] == node[2]:
            merged[-1][1] += node[1]
        else:
            merged.append(node)

    return merged


def pack_images(images_to_pack: list, gang_width: int,
                max_gang_height: int) -> tuple[list, list]:
    """
    Main entry point for the bin-packing algorithm.

    Args:
        images_to_pack: List of dicts with keys: 'image' (PIL Image), 'w', 'h'
        gang_width:     Sheet width in pixels
        max_gang_height: Maximum sheet height in pixels

    Returns:
        (pages, unpacked)
        - pages: list of pages, each page is a list of placement dicts
                 with keys: image, x, y, w, h
        - unpacked: list of images that couldn't fit on any page
    """
    # Sort largest-area first for better packing efficiency
    remaining = sorted(images_to_pack, key=lambda x: x['w'] * x['h'], reverse=True)
    pages = []

    while remaining:
        skyline = [[0, gang_width, 0]]
        placed_this_page = []
        still_remaining = []

        for item in remaining:
            result = _find_best_position(
                skyline, item['w'], item['h'], gang_width, max_gang_height
            )

            if result is None:
                still_remaining.append(item)
                continue

            place_x, place_y, place_w, place_h, rotate = result

            final_img = item['image']
            if rotate:
                final_img = final_img.transpose(Image.Transpose.ROTATE_90)

            placed_this_page.append({
                'image': final_img,
                'x': place_x,
                'y': place_y,
                'w': place_w,
                'h': place_h,
            })

            skyline = _update_skyline(skyline, place_x, place_y, place_w, place_h)

        # If nothing was placed this iteration, remaining images are too large
        if not placed_this_page:
            return pages, still_remaining

        pages.append(placed_this_page)
        remaining = still_remaining

    return pages, []