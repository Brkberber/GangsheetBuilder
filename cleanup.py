# ============================================================
# cleanup.py — Automatic disk cleanup utilities
# ============================================================

import os
import shutil
import time
from threading import Thread
from config import MAX_FILE_AGE_SECONDS, CLEANUP_INTERVAL_SECONDS


def clear_directory(folder_path: str) -> None:
    """Deletes all files and subdirectories inside a folder."""
    if not os.path.exists(folder_path):
        return
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"[CLEANUP] Failed to delete {file_path}: {e}")


def _cleanup_worker(folders: list[str]) -> None:
    """
    Background thread: deletes files older than MAX_FILE_AGE_SECONDS
    from the given folders, running every CLEANUP_INTERVAL_SECONDS.
    """
    while True:
        try:
            current_time = time.time()
            for folder in folders:
                if not os.path.exists(folder):
                    continue
                for filename in os.listdir(folder):
                    if filename.startswith('.'):
                        continue
                    file_path = os.path.join(folder, filename)
                    if os.path.isfile(file_path):
                        age = current_time - os.path.getmtime(file_path)
                        if age > MAX_FILE_AGE_SECONDS:
                            os.remove(file_path)
                            print(f"[CLEANUP] Deleted expired file: {file_path}")
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")

        time.sleep(CLEANUP_INTERVAL_SECONDS)


def start_cleanup_worker(folders: list[str]) -> None:
    """Starts the background cleanup thread (daemon — stops with the app)."""
    thread = Thread(target=_cleanup_worker, args=(folders,), daemon=True)
    thread.start()
    print("[STARTUP] Background cleanup worker started.")