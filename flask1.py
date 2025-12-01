import os
import json
import subprocess
import signal
import csv
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, send_file

UPLOAD_FOLDER = 'static/uplioads'
RESULT_FOLDER = 'static/results'
META_FILE = 'files_meta.json'
STATUS_FILE = 'static/status/process_status.json'
USER_SETTINGS_FILE = "user_settings.json"
MAPSNAPS_FOLDER = 'static/map_snaps'
MAPSNAPS_META = 'static/map_snaps/snaps_meta.json'

app = Flask(__name__)
app.secret_key = "tajny_klucz"
os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
for folder in [UPLOAD_FOLDER, RESULT_FOLDER, MAPSNAPS_FOLDER]:
    os.makedirs(folder, exist_ok=True)
if not os.path.exists(META_FILE):
    with open(META_FILE, 'w') as f:
        json.dump({}, f)
if not os.path.exists(MAPSNAPS_META):
    with open(MAPSNAPS_META, 'w') as f:
        json.dump([], f)

def nowstr():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_meta():
    with open(META_FILE, 'r') as f:
        return json.load(f)

def save_meta(meta):
    with open(META_FILE, 'w') as f:
        json.dump(meta, f, indent=2)

def convert_avi_to_mp4(avi_path, mp4_path):
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', avi_path, '-c:v', 'libx264', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '128k', mp4_path
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        print("FFmpeg error:", e)
        return False

def get_process_status(filename):
    if not os.path.exists(STATUS_FILE):
        return {}
    with open(STATUS_FILE) as f:
        data = json.load(f)
    return data.get(filename, {})

def save_process_status(filename, status):
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r') as f:
                data = json.load(f)
        else:
            data = {}
        data[filename] = status
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print("save_process_status error", e)

def get_user_settings():
    if os.path.exists(USER_SETTINGS_FILE):
        with open(USER_SETTINGS_FILE,"r",encoding="utf8") as f:
            return json.load(f)
    return {
        "theme": "light",
        "font_size": "normal",
        "tooltips": True,
        "mail_notify": False,
        "keep_files": True,
        "error_alert": 3,
        "beta": False,
        "tags": True,
        "lang": "pl",
        "tz": "Europe/Warsaw",
        "dates": "rel"
    }

def save_user_settings(settings):
    with open(USER_SETTINGS_FILE,"w",encoding="utf8") as f:
        json.dump(settings, f, indent=2)

@app.context_processor
def inject_version():
    return dict(app_version="v1.0.1")

@app.route('/')
@app.route('/dashboard')
def dashboard():
    meta = get_meta()
    liczba_plikow = len(meta)
    liczba_analiz = sum(1 for d in meta.values() if d.get('data_analizy'))
    liczba_bledow = sum(1 for d in meta.values() if d.get('status') == 'error')

    analiz_dzis = 2
    analiz_tydzien = 5

    najaktywniejszy = {"imie": "Anna", "akcje": 4, "gender": "f"}
    sukces_pct = 83

    aktywnosc = [
        {"imie": "Anna", "akcja": "Dodała wideo", "data": "2025-11-21 12:32", "status": "Aktywne"},
        {"imie": "Piotr", "akcja": "Uruchomił analizę", "data": "2025-11-21 12:35", "status": "W toku"},
        {"imie": "Ela", "akcja": "Plik PDF", "data": "2025-11-22 10:05", "status": "Błąd"},
    ]
    wydarzenia = [
        {"typ": "success", "tytul": "Analiza pliku zakończona", "data": "2025-11-21 12:40"},
        {"typ": "info", "tytul": "Nowy plik dodany", "data": "2025-11-21 12:35"},
        {"typ": "error", "tytul": "Błąd analizy PDF", "data": "2025-11-21 11:28"},
    ]

    return render_template('dashboard.html',
        liczba_plikow=liczba_plikow,
        liczba_analiz=liczba_analiz,
        liczba_bledow=liczba_bledow,
        analiz_dzis=analiz_dzis,
        analiz_tydzien=analiz_tydzien,
        najaktywniejszy=najaktywniejszy,
        sukces_pct=sukces_pct,
        aktywnosc=aktywnosc,
        wydarzenia=wydarzenia
    )

@app.route('/files', methods=['GET', 'POST'])
def files():
    meta = get_meta()
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Brak pliku!')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Nie wybrano pliku!')
            return redirect(request.url)
        filename = os.path.basename(file.filename).replace(' ', '_')
        file_ext = filename.rsplit('.', 1)[-1].lower()
        orig_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(orig_path)
        now_s = nowstr()
        if file_ext == 'avi':
            mp4file = filename.rsplit('.', 1)[0] + ".mp4"
            mp4path = os.path.join(UPLOAD_FOLDER, mp4file)
            if convert_avi_to_mp4(orig_path, mp4path):
                meta[mp4file] = {
                    "data_dodania": now_s,
                    "data_analizy": "",
                    "status": "oczekuje"
                }
                save_meta(meta)
                flash(f'AVI {filename} przekonwertowano do MP4: {mp4file}')
                os.remove(orig_path)
            else:
                flash('Błąd konwersji AVI do MP4!')
        else:
            meta[filename] = {
                "data_dodania": now_s,
                "data_analizy": "",
                "status": "oczekuje"
            }
            save_meta(meta)
            flash('Plik wrzucony: ' + filename)
        return redirect(url_for('files'))
    files = [
        {
            "nazwa": f,
            "data_dodania": meta.get(f, {}).get('data_dodania', '-'),
            "data_analizy": meta.get(f, {}).get('data_analizy', '-'),
            "status": ("Oczekuje na analizę AI"
                if meta.get(f, {}).get('status', 'oczekuje') == 'oczekuje'
                else meta.get(f, {}).get('status', 'oczekuje')
            )
        }
        for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith(('.mp4', '.webm', '.ogg'))
    ]
    return render_template('files.html', files=files)

@app.route('/analyze')
def analyze():
    meta = get_meta()
    files = [
        {
            "nazwa": f,
            "data_dodania": meta.get(f, {}).get('data_dodania', '-'),
            "data_analizy": meta.get(f, {}).get('data_analizy', '-'),
            "status": meta.get(f, {}).get('status', 'oczekuje')
        }
        for f in os.listdir(UPLOAD_FOLDER)
    ]
    results = os.listdir(RESULT_FOLDER)
    return render_template('analyze.html', files=files, results=results)

@app.route('/start_analysis/<filename>', methods=['POST'])
def start_analysis(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    process = subprocess.Popen(["python", "run_yolo_script.py", filepath, filename])
    save_process_status(filename, {"pid": process.pid, "progress": 0, "stopped": False, "done": False})
    return jsonify(success=True)

@app.route('/stop_analysis/<filename>', methods=['POST'])
def stop_analysis(filename):
    status = get_process_status(filename)
    pid = status.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            save_process_status(filename, {"pid": pid, "progress": status.get("progress", 0), "stopped": True, "done": False})
            return jsonify(stopped=True)
        except Exception as e:
            print("Stop failed", e)
    return jsonify(stopped=False)

@app.route('/progress/<filename>')
def progress(filename):
    return jsonify(get_process_status(filename))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/result/<filename>')
def result(filename):
    return send_from_directory(RESULT_FOLDER, filename)

@app.route('/tools')
def tools():
    return render_template('tools.html')

@app.route('/reports')
def reports():
    meta = get_meta()
    start = request.args.get('start')
    end = request.args.get('end')
    user = request.args.get('user')
    status_filter = request.args.get('status')
    phrase = request.args.get('q', '').lower()
    today = datetime.today()
    if not end:
        end = today.strftime('%Y-%m-%d')
    if not start:
        start = (today - timedelta(days=6)).strftime('%Y-%m-%d')
    daty = {'start': start, 'end': end}

    all_users = list({d.get('user','Anna') for d in meta.values()}) + ['Piotr', 'Ela']
    statusy = ['success', 'error', 'active']

    rekordy = [
        {"data": "2025-11-21 11:40", "user": "Anna", "akcja": "Analiza pliku", "status": "success"},
        {"data": "2025-11-21 11:31", "user": "Piotr", "akcja": "Dodano plik", "status": "success"},
        {"data": "2025-11-21 11:29", "user": "Anna", "akcja": "Analiza pliku", "status": "active"},
        {"data": "2025-11-21 11:28", "user": "Ela", "akcja": "Analiza PDF", "status": "error"},
    ]

    records_filtered = []
    for r in rekordy:
        is_ok = True
        dt = r['data'][:10]
        if dt < start or dt > end:
            is_ok = False
        if user and r["user"] != user:
            is_ok = False
        if status_filter and r["status"] != status_filter:
            is_ok = False
        if phrase and phrase not in r["akcja"].lower() and phrase not in r["user"].lower():
            is_ok = False
        if is_ok:
            records_filtered.append(r)

    user_stats = {}
    for r in rekordy:
        user_stats.setdefault(r['user'],0)
        user_stats[r['user']] += 1
    top_users = sorted(user_stats.items(),key=lambda x:x[1], reverse=True)[:5]

    podsumowanie = {
        'analiz': len(records_filtered),
        'zakonczone': sum(1 for r in records_filtered if r['status'] == 'success'),
        'bledy': sum(1 for r in records_filtered if r['status'] == 'error'),
        'userow': len(set(r['user'] for r in records_filtered)),
        'efektywnosc': round(
            100*sum(1 for r in records_filtered if r['status'] == 'success')/(len(records_filtered) or 1) , 2)
    }
    trendy = {
        'labels': ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Nd'],
        'values': [2, 1, 3, 4, 2, 0, 1]
    }
    heatmap = list(zip(trendy['labels'], trendy['values']))
    alert = None
    if podsumowanie["efektywnosc"] < 70:
        alert = "Alert: Skuteczność analiz spadła poniżej 70%!"

    return render_template('reports.html',
        daty=daty,
        podsumowanie=podsumowanie,
        trendy=trendy,
        heatmap=heatmap,
        rekordy=records_filtered,
        all_users=all_users,
        statusy=statusy,
        phrase=phrase or '',
        filter_user=user or '',
        filter_status=status_filter or '',
        top_users=top_users,
        alert=alert
    )

@app.route('/export_csv')
def export_csv():
    start = request.args.get('start')
    end = request.args.get('end')
    user = request.args.get('user')
    status_filter = request.args.get('status')
    phrase = request.args.get('q', '').lower()
    rekordy = [
        {"data": "2025-11-21 11:40", "user": "Anna", "akcja": "Analiza pliku", "status": "success"},
        {"data": "2025-11-21 11:31", "user": "Piotr", "akcja": "Dodano plik", "status": "success"},
        {"data": "2025-11-21 11:29", "user": "Anna", "akcja": "Analiza pliku", "status": "active"},
        {"data": "2025-11-21 11:28", "user": "Ela", "akcja": "Analiza PDF", "status": "error"},
    ]
    records_filtered = []
    for r in rekordy:
        is_ok = True
        dt = r['data'][:10]
        if start and dt < start:
            is_ok = False
        if end and dt > end:
            is_ok = False
        if user and r['user'] != user:
            is_ok = False
        if status_filter and r["status"] != status_filter:
            is_ok = False
        if phrase and phrase not in r["akcja"].lower() and phrase not in r["user"].lower():
            is_ok = False
        if is_ok:
            records_filtered.append(r)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Data', 'Użytkownik', 'Operacja', 'Status'])
    for r in records_filtered:
        writer.writerow([r['data'], r['user'], r['akcja'], r['status']])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), as_attachment=True,
                     download_name='raport.csv', mimetype='text/csv')

@app.route('/export_xlsx')
def export_xlsx():
    import xlsxwriter
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    worksheet.write_row(0,0, ['Data', 'Użytkownik', 'Operacja', 'Status'])
    data = [
        ["2025-11-21 11:40", "Anna", "Analiza pliku", "success"],
        ["2025-11-21 11:29", "Anna", "Analiza pliku", "active"]
    ]
    for idx,row in enumerate(data,1):
        worksheet.write_row(idx,0,row)
    workbook.close()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="raport.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route('/export_pdf')
def export_pdf():
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(60, 10, 'Raport Analiz', ln=True)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, 'To tylko przykładowy PDF wygenerowany w Flask.', ln=True)
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="raport.pdf", mimetype="application/pdf")

@app.route('/settings', methods=['GET','POST'])
def settings():
    s = get_user_settings()
    if request.method == "POST":
        if "save_ui" in request.form:
            s["theme"] = request.form.get("theme","light")
            s["font_size"] = request.form.get("font_size","normal")
            s["tooltips"] = "tooltips" in request.form
        if "save_acc" in request.form:
            pass
        if "save_priv" in request.form:
            s["keep_files"] = "keep_files" in request.form
            s["mail_notify"] = "mail_notify" in request.form
            try:
                s["error_alert"] = int(request.form.get("error_alert") or 3)
            except:
                s["error_alert"] = 3
        if "save_adv" in request.form:
            s["beta"] = "beta" in request.form
            s["tags"] = "tags" in request.form
        if "save_time" in request.form:
            s["lang"] = request.form.get("lang", "pl")
            s["tz"] = request.form.get("tz", "Europe/Warsaw")
            s["dates"] = request.form.get("dates", "rel")
        if "export_data" in request.form:
            flash("Eksport danych niezaimplementowany w demie.", "info")
        if "delete_acc" in request.form:
            os.remove(USER_SETTINGS_FILE)
            flash("Konto i ustawienia usunięte!", "danger")
            return redirect(url_for("settings"))
        save_user_settings(s)
        flash("Ustawienia zostały zapisane.", "success")
        return redirect(url_for("settings"))
    return render_template('settings.html', s=s)

@app.route('/history')
def history():
    meta = get_meta()
    h = sorted(
        [{"nazwa":k, **v} for k,v in meta.items()], #gites działa
        key=lambda d: d['data_dodania'], reverse=True
    )
    return render_template('history.html', files=h[:10])

@app.route('/help')
def help():
    return render_template('help.html')
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        with open('kontakt.txt', 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now()} | {name} | {email} | {message}\n")
        flash('Dziękujemy za wiadomość! Skontaktujemy się wkrótce.', 'info')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/chat_api')
def chat_api():
    msg = request.args.get('msg','').lower()
    if 'stary' in msg:
        reply = 'Twój stary programował w Assemblerze bez debuggera 😎'
    elif 'yolo' in msg:
        reply = 'YOLO to model wykrywania obiektów, Twój projekt świetnie go wykorzystuje!'
    elif 'quiz' in msg:
        reply = 'Quiz? Spróbuj: Ile warstw ma typowa sieć CNN?'
    elif 'motywacja' in msg:
        reply = 'Nigdy się nie poddawaj! Nawet AI czasem ma gorszy dzień.'
    elif 'matematyka' in msg:
        reply = 'W czym mogę pomóc matematycznie? Dodawanie, całki, relacje?'
    elif 'dowcip' in msg or 'żart' in msg:
        reply = 'Dlaczego sieć neuronowa ma dobry humor? Bo nigdy nie boi się zgubić w głębi!'
    else:
        reply = 'Jestem Twoim czatbotem AI – pytaj o projekt, YOLO albo po prostu zadaj mi dowolne pytanie!'
    return jsonify(reply=reply)

@app.route('/map', methods=['GET'])
def map_view():
    if os.path.exists(MAPSNAPS_META):
        with open(MAPSNAPS_META, 'r') as f:
            snaps = json.load(f)
    else:
        snaps = []
    return render_template('map.html', snaps=snaps)

@app.route('/upload_map_snap', methods=['POST'])
def upload_map_snap():
    file = request.files.get('img')
    if not file:
        return jsonify(success=0, error="No file"), 400
    username = request.form.get('username', "Nieznany")
    customname = request.form.get('filename', "").strip()
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if customname:
        fname = customname if customname.lower().endswith('.png') else (customname + '.png')
    else:
        fname = f"zrzut_mapy_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.png"
    path = os.path.join('static/map_snaps', fname)
    file.save(path)
    meta = []
    if os.path.exists('static/map_snaps/snaps_meta.json'):
        with open('static/map_snaps/snaps_meta.json', 'r') as f:
            meta = json.load(f)
    meta.insert(0, {
        "filename": fname,
        "user": username,
        "date": dt
    })
    with open('static/map_snaps/snaps_meta.json', 'w') as f:
        json.dump(meta, f, indent=2)
    return jsonify(success=1, filename=fname)

@app.route('/map_snap/<filename>')
def map_snap(filename):
    return send_from_directory(MAPSNAPS_FOLDER, filename)

@app.route('/delete_map_snap', methods=['POST'])
def delete_map_snap():
    data = request.get_json()
    fname = data.get('filename')
    path = os.path.join('static/map_snaps', fname)
    meta = []
    if os.path.exists('static/map_snaps/snaps_meta.json'):
        with open('static/map_snaps/snaps_meta.json', 'r') as f:
            meta = json.load(f)
    meta = [snap for snap in meta if snap['filename'] != fname]
    with open('static/map_snaps/snaps_meta.json', 'w') as f:
        json.dump(meta, f, indent=2)
    if os.path.exists(path): os.remove(path)
    return jsonify(success=1)

app.run(debug=True)
