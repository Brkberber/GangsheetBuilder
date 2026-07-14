<div align="center">

# 🖨️ GangsheetBuilder

**A production-ready web app for automatically packing print-ready gang sheets — built for real DTF/DTG printing workflows.**

[![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Pillow](https://img.shields.io/badge/Pillow-3776AB?style=flat-square&logo=python&logoColor=white)](https://pillow.readthedocs.io)
[![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white)](https://opencv.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

---

## 🧠 What Is a Gang Sheet?

In DTF (Direct to Film) and DTG (Direct to Garment) printing, a **gang sheet** is a single large print canvas where multiple designs are packed as tightly as possible to minimize wasted material. Arranging dozens of designs manually — at precise DPI, in the right dimensions, without overlap — is slow and error-prone.

**GangsheetBuilder automates all of it.**

---

## ✨ Features

### 🔲 Custom Skyline Bin-Packing Algorithm
At the core of GangsheetBuilder is a **custom-built 2D skyline bin-packing algorithm** — written from scratch without relying on external packing libraries. It:
- Places each design in the position that minimizes wasted vertical space
- Automatically **rotates designs 90°** when it finds a better fit
- **Overflows to multiple pages** when designs don't fit on a single sheet
- Sorts by area descending for optimal placement efficiency

### 🎨 Print-Ready Output
- Outputs at **300 DPI** — industry standard for DTF/DTG printing
- Applies **CMYK color correction** before saving to ensure color accuracy on press
- Preserves **transparency (alpha channel)** through the CMYK conversion pipeline
- Saves each page as a high-resolution **PNG** and packages everything into a **ZIP**

### ⚡ Smart Image Processing
- Auto-crops transparent borders on upload (tight bounding box)
- Detects whether images have transparent backgrounds
- Calculates **sharpness scores** via Laplacian variance (OpenCV) to flag low-quality uploads
- Reports original pixel dimensions and inch dimensions at 300 DPI

### 🔒 Production-Ready Architecture
- **UUID-based filenames** prevent collisions when multiple users run simultaneously
- **Directory traversal protection** on the file delete endpoint
- **Startup disk wipe** — uploads and outputs are cleared on every server restart
- **Background garbage collector** — automatically deletes files older than 30 minutes
- Configurable sheet width, max sheet height, padding, and quantity per design

---

## 🖥️ How It Works

```
User uploads designs (PNG/transparent)
        ↓
Server auto-crops, measures, scores sharpness
        ↓
User sets: target width (inches) + quantity per design
        ↓
Skyline bin-packing algorithm places designs optimally
  → Tries both normal and 90° rotated orientation
  → Overflows to new pages if needed
        ↓
CMYK color correction applied to each page
        ↓
Pages saved as 300 DPI PNGs → zipped → downloaded
```

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3, Flask |
| Image Processing | Pillow (PIL), OpenCV |
| Packing Algorithm | Custom skyline bin-packing (no library) |
| Frontend | HTML, CSS, JavaScript |
| Output Format | PNG (300 DPI, RGBA) → ZIP |

---

## ⚙️ Getting Started

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/Brkberber/GangsheetBuilder.git
cd GangsheetBuilder

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```

Then open [http://localhost:5002](http://localhost:5002) in your browser.

### Requirements

```
flask
pillow
opencv-python
numpy
```

---

## 📁 Project Structure

```
GangsheetBuilder/
├── main.py          
├── packing.py       
├── image_utils.py   
├── cleanup.py       
├── config.py        
├── requirements.txt 
├── .gitignore       
├── README.md        
└── templates/
    └── index.html   
```

---

## 🔧 Configuration

Key parameters are set per-request from the UI, with these defaults:

| Parameter | Default | Description |
|---|---|---|
| Sheet width | 22 inches | Standard DTF roll width |
| Max sheet height | 250 inches | Maximum gang sheet length |
| Padding | 0.25 inches | Gap between designs |
| DPI | 300 | Output resolution |
| File expiry | 30 minutes | Auto-cleanup age threshold |

---

## 🚀 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | GET | Main UI — also flushes uploads/output on load |
| `POST /upload-files` | POST | Upload and process image files |
| `POST /delete-file` | POST | Delete a single uploaded file from disk |
| `POST /generate-gangsheet` | POST | Run the packing algorithm and generate output |
| `GET /download/<filename>` | GET | Download the generated ZIP file |

---

## 💡 Why a Custom Algorithm?

Off-the-shelf bin-packing libraries don't account for:
- Print-specific constraints (fixed sheet width, variable height)
- Per-design quantity multipliers
- Rotation as an optimization strategy
- Multi-page overflow with consistent padding

The skyline algorithm implemented here handles all of these while remaining fast enough for real-time use in a web app.

---

## 👨‍💻 Developer

Built by **Burak Berber** — Civil Engineering student at Boğaziçi University, self-taught developer.  
Developed and used in a real production printing workflow.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/brk-berber)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Brkberber)
