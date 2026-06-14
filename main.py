import os
import uuid
import cv2
import zipfile
import numpy as np
import time
import shutil
from threading import Thread
from flask import Flask, render_template, request, send_from_directory, jsonify
from PIL import Image

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER


# =========================================================
# STARTUP CLEANUP: Empty directories every time server starts
# =========================================================
def clear_directory(folder_path):
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path} on startup. Reason: {e}")


# Flush folders immediately upon server startup
clear_directory(UPLOAD_FOLDER)
clear_directory(OUTPUT_FOLDER)

# Ensure fresh directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
print("[STARTUP] Uploads and Output directories have been completely wiped and re-created.")


# =========================================================
# AUTOMATIC BACKGROUND CLEANUP TASK (GARBAGE COLLECTOR)
# =========================================================
def auto_cleanup_worker():
    MAX_FILE_AGE_SECONDS = 30 * 60  # 30 minutes
    while True:
        try:
            current_time = time.time()
            for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
                if not os.path.exists(folder):
                    continue
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    if filename.startswith('.'):
                        continue
                    if os.path.isfile(file_path):
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > MAX_FILE_AGE_SECONDS:
                            os.remove(file_path)
                            print(f"[CLEANUP] Deleted old file: {file_path}")
        except Exception as e:
            print(f"[CLEANUP ERROR] Failed during automated disk cleaning: {e}")
        time.sleep(10 * 60)


cleanup_thread = Thread(target=auto_cleanup_worker, daemon=True)
cleanup_thread.start()


def has_transparent_background(img):
    if img.mode != 'RGBA':
        return False
    alpha = img.getchannel('A')
    extrema = alpha.getextrema()
    if extrema[0] == 255:
        return False
    return True


@app.route('/')
def index():
    clear_directory(app.config['UPLOAD_FOLDER'])
    clear_directory(app.config['OUTPUT_FOLDER'])
    print("[REFRESH CLEANUP] Uploads and Output directories have been flushed due to page reload.")

    return render_template('index.html')


@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/upload-files', methods=['POST'])
def upload_files():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files[]')
    file_data = []
    dpi = 300

    for file in files:
        if file.filename == '':
            continue

        base_filename = os.path.splitext(file.filename)[0]
        unique_filename = f"{uuid.uuid4().hex}_{base_filename}.png"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        try:
            file.save(filepath)

            with Image.open(filepath).convert("RGBA") as img:
                bbox = img.getbbox()
                if bbox:
                    img_cropped = img.crop(bbox)
                    orig_w, orig_h = img_cropped.size
                    img_cropped.save(filepath, format="PNG")
                else:
                    orig_w, orig_h = img.size
                    img.save(filepath, format="PNG")

                is_transparent = has_transparent_background(img_cropped if bbox else img)

            img_cv = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
            if img_cv is not None:
                sharpness_score = cv2.Laplacian(img_cv, cv2.CV_64F).var()
            else:
                sharpness_score = 500

            file_data.append({
                'filename': unique_filename,
                'display_name': file.filename,
                'orig_w_px': orig_w,
                'orig_h_px': orig_h,
                'orig_w_inch': round(orig_w / dpi, 2),
                'orig_h_inch': round(orig_h / dpi, 2),
                'is_transparent': is_transparent,
                'sharpness': round(sharpness_score, 1)
            })
        except Exception as e:
            print(f"Error processing {file.filename}: {e}")

    return jsonify({'files': file_data})


# =========================================================
# NEW ROUTE: Instantly delete single file from disk when user clicks 'Delete'
# =========================================================
@app.route('/delete-file', methods=['POST'])
def delete_file():
    data = request.json or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400

    # Security check: prevent directory traversal attacks
    clean_filename = os.path.basename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], clean_filename)

    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"[API DELETE] File successfully deleted from disk: {filepath}")
            return jsonify({'success': True, 'message': 'File deleted from server disk'})
        return jsonify({'error': 'File not found on disk'}), 404
    except Exception as e:
        print(f"[API DELETE ERROR] Failed to delete file {clean_filename}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/generate-gangsheet', methods=['POST'])
def generate_gangsheet():
    data = request.json
    configs = data.get('configs', [])
    sheet_width_inch = float(data.get('sheet_width', 22))
    max_sheet_height_inch = float(data.get('max_sheet_height', 250))
    dpi = 300

    pixel_per_inch = dpi
    gang_width_px = int(sheet_width_inch * pixel_per_inch)
    max_gang_height_px = int(max_sheet_height_inch * pixel_per_inch)
    padding_px = int(0.25 * pixel_per_inch)

    images_to_pack = []

    for index, item in enumerate(configs):
        filename = item['filename']
        target_w_inch = float(item['target_value'])
        quantity = int(item['quantity'])

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            continue

        with Image.open(filepath) as img:
            orig_w, orig_h = img.size
            aspect_ratio = orig_h / orig_w
            target_h_inch = target_w_inch * aspect_ratio

            target_w_px = int(target_w_inch * pixel_per_inch)
            target_h_px = int(target_h_inch * pixel_per_inch)

            resized_img = img.resize((target_w_px, target_h_px), Image.Resampling.LANCZOS)

            for i in range(quantity):
                images_to_pack.append({
                    'image': resized_img,
                    'w': target_w_px + (padding_px * 2),
                    'h': target_h_px + (padding_px * 2)
                })

    if not images_to_pack:
        return jsonify({'error': 'No valid images to layout'}), 400

    images_to_pack.sort(key=lambda x: x['w'] * x['h'], reverse=True)

    pages = []

    while len(images_to_pack) > 0:
        skyline = [[0, gang_width_px, 0]]
        current_page_images = []
        remaining_images_for_next_pages = []

        for item in images_to_pack:
            img_w = item['w']
            img_h = item['h']

            best_skyline_idx = -1
            best_y = float('inf')
            best_w, best_h = img_w, img_h
            best_x = 0
            rotate_needed = False

            for i in range(len(skyline)):
                x_pos = skyline[i][0]

                if x_pos + img_w <= gang_width_px:
                    max_y = 0
                    w_left = img_w
                    curr_idx = i
                    while w_left > 0 and curr_idx < len(skyline):
                        max_y = max(max_y, skyline[curr_idx][2])
                        w_left -= skyline[curr_idx][1]
                        curr_idx += 1

                    if w_left <= 0 and (max_y + img_h <= max_gang_height_px):
                        if max_y + img_h < best_y:
                            best_y = max_y + img_h
                            best_skyline_idx = i
                            best_x = x_pos
                            best_w, best_h = img_w, img_h
                            rotate_needed = False

                if x_pos + img_h <= gang_width_px:
                    max_y = 0
                    w_left = img_h
                    curr_idx = i
                    while w_left > 0 and curr_idx < len(skyline):
                        max_y = max(max_y, skyline[curr_idx][2])
                        w_left -= skyline[curr_idx][1]
                        curr_idx += 1

                    if w_left <= 0 and (max_y + img_w <= max_gang_height_px):
                        if max_y + img_w < best_y:
                            best_y = max_y + img_w
                            best_skyline_idx = i
                            best_x = x_pos
                            best_w, best_h = img_h, img_w
                            rotate_needed = True

            if best_skyline_idx != -1:
                actual_y = best_y - best_h

                final_img = item['image']
                if rotate_needed:
                    final_img = final_img.transpose(Image.Transpose.ROTATE_90)

                current_page_images.append({
                    'image': final_img,
                    'x': best_x,
                    'y': actual_y,
                    'w': best_w,
                    'h': best_h
                })

                new_node = [best_x, best_w, best_y]
                new_skyline = []
                for node in skyline:
                    node_x, node_w, node_y = node
                    if node_x >= best_x + best_w or node_x + node_w <= best_x:
                        new_skyline.append(node)
                    else:
                        if node_x < best_x:
                            new_skyline.append([node_x, best_x - node_x, node_y])
                        if node_x + node_w > best_x + best_w:
                            new_skyline.append([best_x + best_w, (node_x + node_w) - (best_x + best_w), node_y])

                new_skyline.append(new_node)
                new_skyline.sort(key=lambda x: x[0])

                merged = []
                for node in new_skyline:
                    if not merged:
                        merged.append(node)
                    else:
                        prev = merged[-1]
                        if prev[0] + prev[1] == node[0] and prev[2] == node[2]:
                            prev[1] += node[1]
                        else:
                            merged.append(node)
                skyline = merged
            else:
                remaining_images_for_next_pages.append(item)

        if not current_page_images and remaining_images_for_next_pages:
            return jsonify({'error': 'A single design is larger than the maximum allowed sheet length.'}), 400

        pages.append(current_page_images)
        images_to_pack = remaining_images_for_next_pages

    zip_unique_id = uuid.uuid4().hex
    zip_filename = f"gangsheet_pack_{zip_unique_id}.zip"
    zip_path = os.path.join(app.config['OUTPUT_FOLDER'], zip_filename)

    total_height_inch_all_pages = 0
    generated_file_paths = []

    for idx, page_images in enumerate(pages):
        page_height_px = max([p['y'] + p['h'] for p in page_images]) if page_images else 1
        total_height_inch_all_pages += (page_height_px / pixel_per_inch)

        temp_rgba_canvas = Image.new("RGBA", (gang_width_px, page_height_px), (0, 0, 0, 0))
        for pi in page_images:
            temp_rgba_canvas.paste(pi['image'], (pi['x'] + padding_px, pi['y'] + padding_px))

        cmyk_version = temp_rgba_canvas.convert("CMYK")
        cmyk_corrected_rgb = cmyk_version.convert("RGB")
        _, _, _, alpha_channel = temp_rgba_canvas.split()

        final_png_canvas = Image.merge("RGBA", (
            cmyk_corrected_rgb.getchannel('R'),
            cmyk_corrected_rgb.getchannel('G'),
            cmyk_corrected_rgb.getchannel('B'),
            alpha_channel
        ))

        png_filename = f"gangsheet_page_{idx + 1}.png"
        png_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{zip_unique_id}_{png_filename}")
        final_png_canvas.save(png_path, format="PNG", dpi=(dpi, dpi))

        generated_file_paths.append((png_path, png_filename))

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for full_path, archive_name in generated_file_paths:
            zip_file.write(full_path, archive_name)
            if os.path.exists(full_path):
                os.remove(full_path)

    return jsonify({
        'download_url': f"/download/{zip_filename}",
        'is_zip': True,
        'total_pages': len(pages),
        'width_inch': sheet_width_inch,
        'height_inch': round(total_height_inch_all_pages, 2),
        'width_cm': round(sheet_width_inch * 2.54, 1),
        'height_cm': round(total_height_inch_all_pages * 2.54, 1)
    })


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, port=5002)