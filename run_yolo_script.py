import sys
import time
import json
import os
import signal
import portalocker
from ultralytics import YOLO

UPLOAD_FOLDER = "static/uploads"
RESULT_FOLDER = "static/results"
PROCESS_STATUS_FILE = "static/status/process_status.json"
MODEL_PATH = os.path.join("models", "best.pt")

def update_progress(filename, percent, stopped=False, done=False):
    status_file = PROCESS_STATUS_FILE
    if os.path.exists(status_file):
        with open(status_file, 'r+') as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            try:
                try:
                    data = json.load(f)
                except Exception:
                    data = {}
                val = data.get(filename, {})
                val['progress'] = percent
                val['stopped'] = stopped
                val['done'] = done
                data[filename] = val
                f.seek(0)
                f.truncate()
                json.dump(data, f)
                f.flush()
            finally:
                portalocker.unlock(f)
    else:
        with open(status_file, 'w') as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            json.dump({filename: {"progress": percent, "stopped": stopped, "done": done}}, f)
            f.flush()
            portalocker.unlock(f)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("usage: run_yolo_script.py filepath filename")
        sys.exit(1)
    filepath = sys.argv[1]
    filename = sys.argv[2]
    model = YOLO(MODEL_PATH)
    STOPPED = False

    def handle_term(signum, frame):
        global STOPPED
        STOPPED = True
        update_progress(filename, percent=0, stopped=True, done=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_term)

    # Symulacja progresu
    for i in range(1, 96):
        if STOPPED:
            update_progress(filename, i, stopped=True, done=False)
            break
        update_progress(filename, i)
        time.sleep(0.08)

    # Analiza YOLO
    if not STOPPED:
        results = model(filepath, save=True, project=RESULT_FOLDER, name="wyniki")
        update_progress(filename, 100, done=True)
