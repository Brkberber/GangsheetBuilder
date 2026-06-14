# ============================================================
# image_utils.py — Image processing utilities
# ============================================================

import cv2
import numpy as np
from PIL import Image
from config import DPI


def has_transparent_background(img: Image.Image) -> bool:
    """Returns True if the image has any transparency (non-255 alpha pixels)."""
    if img.mode != 'RGBA':
        return False
    alpha = img.getchannel('A')
    return alpha.getextrema()[0] < 255


def get_sharpness_score(filepath: str) -> float:
    """
    Calculates image sharpness using Laplacian variance (OpenCV).
    Higher score = sharper image. Returns 500.0 if image can't be read.
    """
    img_cv = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
    if img_cv is not None:
        return round(cv2.Laplacian(img_cv, cv2.CV_64F).var(), 1)
    return 500.0


def process_upload(filepath: str, original_filename: str) -> dict:
    """
    Opens an uploaded image, auto-crops transparent borders,
    saves the cleaned version back to disk, and returns metadata.
    """
    with Image.open(filepath).convert("RGBA") as img:
        bbox = img.getbbox()
        if bbox:
            img_cropped = img.crop(bbox)
            orig_w, orig_h = img_cropped.size
            img_cropped.save(filepath, format="PNG")
            is_transparent = has_transparent_background(img_cropped)
        else:
            orig_w, orig_h = img.size
            img.save(filepath, format="PNG")
            is_transparent = has_transparent_background(img)

    sharpness = get_sharpness_score(filepath)

    return {
        'orig_w_px': orig_w,
        'orig_h_px': orig_h,
        'orig_w_inch': round(orig_w / DPI, 2),
        'orig_h_inch': round(orig_h / DPI, 2),
        'is_transparent': is_transparent,
        'sharpness': sharpness,
    }


def apply_cmyk_correction(rgba_canvas: Image.Image) -> Image.Image:
    """
    Converts an RGBA canvas through CMYK and back to RGB,
    then reattaches the original alpha channel.
    This corrects colors for print-accurate output.
    """
    cmyk = rgba_canvas.convert("CMYK")
    corrected_rgb = cmyk.convert("RGB")
    _, _, _, alpha = rgba_canvas.split()

    return Image.merge("RGBA", (
        corrected_rgb.getchannel('R'),
        corrected_rgb.getchannel('G'),
        corrected_rgb.getchannel('B'),
        alpha
    ))