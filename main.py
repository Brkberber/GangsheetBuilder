# ============================================================
# main.py — Flask application and routes
# ============================================================

import os
import uuid
import zipfile

from flask import Flask, render_template, request, send_from_directory, jsonify
from PIL import Image

from config import (
    DPI, PADDING_INCH,
    DEFAULT_SHEET_WIDTH_INCH, DEFAULT_MAX_SHEET_HEIGHT_INCH,
    UPLOAD_FOLDER, OUTPUT_FOLDER,
)
from cleanup import clear_directory, start_cleanup_worker
from image_utils import process_upload, apply_cmyk_correction
from packing import pack_images

# ── App setup ────────────────────────────────────────────────
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# ── Startup: wipe temp folders, ensure they exist ────────────
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
    clear_directory(folder)
    os.makedirs(folder, exist_ok=True)
print("[STARTUP] Uploads and Output directories wiped and re-created.")

# ── Background garbage collector ─────────────────────────────
start_cleanup_worker([UPLOAD_FOLDER, OUTPUT_FOLDER])


# ── Routes ───────────────────────────────────────────────────

@app.route('/')
def index():
    clear_directory(app.config['UPLOAD_FOLDER'])
    clear_directory(app.config['OUTPUT_FOLDER'])
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

    for file in files:
        if not file.filename:
            continue

        base_filename = os.path.splitext(file.filename)[0]
        unique_filename = f"{uuid.uuid4().hex}_{base_filename}.png"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        try:
            file.save(filepath)
            metadata = process_upload(filepath, file.filename)
            file_data.append({
                'filename': unique_filename,
                'display_name': file.filename,
                **metadata,
            })
        except Exception as e:
            print(f"[UPLOAD ERROR] {file.filename}: {e}")

    return jsonify({'files': file_data})


@app.route('/delete-file', methods=['POST'])
def delete_file():
    data = request.json or {}
    filename = data.get('filename')

    if not filename:
        return jsonify({'error': 'No filename provided'}), 400

    # Security: prevent directory traversal
    clean_filename = os.path.basename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], clean_filename)

    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'success': True})
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate-gangsheet', methods=['POST'])
def generate_gangsheet():
    data = request.json
    configs = data.get('configs', [])

    sheet_width_inch = float(data.get('sheet_width', DEFAULT_SHEET_WIDTH_INCH))
    max_height_inch = float(data.get('max_sheet_height', DEFAULT_MAX_SHEET_HEIGHT_INCH))

    padding_px = int(PADDING_INCH * DPI)
    gang_width_px = int(sheet_width_inch * DPI)
    max_height_px = int(max_height_inch * DPI)

    # ── Build image list ──────────────────────────────────────
    images_to_pack = []
    for item in configs:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], item['filename'])
        if not os.path.exists(filepath):
            continue

        target_w_inch = float(item['target_value'])
        quantity = int(item['quantity'])

        try:
            with Image.open(filepath) as img:
                orig_w, orig_h = img.size
                aspect = orig_h / orig_w
                target_w_px = int(target_w_inch * DPI)
                target_h_px = int(target_w_inch * aspect * DPI)
                resized = img.resize((target_w_px, target_h_px), Image.Resampling.LANCZOS)

                for _ in range(quantity):
                    images_to_pack.append({
                        'image': resized.copy(),
                        'w': target_w_px + padding_px * 2,
                        'h': target_h_px + padding_px * 2,
                    })
        except Exception as e:
            print(f"[GENERATE ERROR] {item['filename']}: {e}")

    if not images_to_pack:
        return jsonify({'error': 'No valid images to layout'}), 400

    # ── Run bin-packing ───────────────────────────────────────
    pages, unpacked = pack_images(images_to_pack, gang_width_px, max_height_px)

    if not pages:
        return jsonify({'error': 'A design is larger than the maximum sheet size.'}), 400

    # ── Render pages and zip ──────────────────────────────────
    zip_id = uuid.uuid4().hex
    zip_filename = f"gangsheet_pack_{zip_id}.zip"
    zip_path = os.path.join(app.config['OUTPUT_FOLDER'], zip_filename)

    total_height_inch = 0
    generated_files = []

    for idx, page in enumerate(pages):
        page_height_px = max(p['y'] + p['h'] for p in page)
        total_height_inch += page_height_px / DPI

        canvas = Image.new("RGBA", (gang_width_px, page_height_px), (0, 0, 0, 0))
        for p in page:
            canvas.paste(p['image'], (p['x'] + padding_px, p['y'] + padding_px))

        final_canvas = apply_cmyk_correction(canvas)

        png_name = f"gangsheet_page_{idx + 1}.png"
        png_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{zip_id}_{png_name}")
        final_canvas.save(png_path, format="PNG", dpi=(DPI, DPI))
        generated_files.append((png_path, png_name))

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for full_path, archive_name in generated_files:
            zf.write(full_path, archive_name)
            if os.path.exists(full_path):
                os.remove(full_path)

    return jsonify({
        'download_url': f"/download/{zip_filename}",
        'is_zip': True,
        'total_pages': len(pages),
        'width_inch': sheet_width_inch,
        'height_inch': round(total_height_inch, 2),
        'width_cm': round(sheet_width_inch * 2.54, 1),
        'height_cm': round(total_height_inch * 2.54, 1),
    })


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, port=5002)