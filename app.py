import os
import threading
import subprocess
import shutil
import time
import json
import urllib.request
from flask import Flask, request, render_template_string, jsonify, redirect, url_for

import logging
app = Flask(__name__)

# --- STOP DE LOG-SPAM VAN DE STATUS ---
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)
# -------------------------------------

# --- DYNAMISCHE FFMPEG PARSER ---
def get_ffmpeg_formats():
    try:
        result = subprocess.run(['ffmpeg', '-formats'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        formats = set()
        for line in result.stdout.splitlines():
            if len(line) > 4 and line[2] == 'E':
                for fmt in line[4:].split()[0].split(','):
                    formats.add(fmt.strip())
        return sorted(list(formats))
    except:
        return ["matroska", "mp4", "avi", "mov", "webm", "ts"]

def get_ffmpeg_codecs(type_char):
    try:
        result = subprocess.run(['ffmpeg', '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        codecs = set(["copy"]) 
        for line in result.stdout.splitlines():
            if len(line) > 8 and line[1] == type_char:
                codecs.add(line[8:].split()[0].strip())
        sorted_codecs = sorted(list(codecs))
        sorted_codecs.insert(0, sorted_codecs.pop(sorted_codecs.index("copy")))
        return sorted_codecs
    except:
        return ["copy", "libx264", "libx265", "aac", "ac3"]

ALL_FORMATS = get_ffmpeg_formats()
ALL_VCODECS = get_ffmpeg_codecs('V')
ALL_ACODECS = get_ffmpeg_codecs('A')

EXT_MAPPING = {
    "matroska": "mkv",
    "ipod": "m4v",
    "mpegts": "ts",
    "asf": "wmv"
}

MEDIA_MAP = "/media"
CACHE_MAP = "/cache"

INITIAL_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

STATE = {
    "is_running": False,
    "status_text": "Klaar voor een nieuwe taak. Selecteer je mappen en klik op Start.",
    "current_file": "-",
    "completed_files": [],
    "failed_files": [],
    "webhook_url": INITIAL_WEBHOOK
}

def get_directory_tree(path=MEDIA_MAP):
    tree = {}
    if not os.path.exists(path):
        return tree
    try:
        with os.scandir(path) as it:
            entries = sorted([entry for entry in it if entry.is_dir()], key=lambda e: e.name.lower())
            for entry in entries:
                tree[entry.name] = get_directory_tree(entry.path)
    except PermissionError:
        pass
    return tree

def send_discord_notification(webhook_url, message):
    print(f"DEBUG: Probeer Discord melding te sturen naar: {webhook_url}", flush=True)
    if not webhook_url or not webhook_url.startswith("http"):
        print("DEBUG: Geen geldige webhook URL opgegeven of URL start niet met http.", flush=True)
        return
    data = {
        "content": message,
        "username": "Ultimate Video Converter",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4204/4204104.png"
    }
    
    # Hier voegen we de User-Agent toe zodat Discord de bot niet weigert
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'UltimateVideoConverter/1.0'
    }
    
    req = urllib.request.Request(webhook_url, data=json.dumps(data).encode('utf-8'), headers=headers)
    try:
        response = urllib.request.urlopen(req)
        print(f"DEBUG: Discord melding succesvol verzonden! Status: {response.getcode()}", flush=True)
    except Exception as e:
        print(f"Fout bij sturen Discord notificatie: {e}", flush=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ultimate Video Converter</title>
    
    <script>
        (function() {
            var userLang = (navigator.language || navigator.userLanguage).split('-')[0];
            if (userLang !== 'nl') {
                var cookieName = 'googtrans';
                var cookieValue = '/nl/' + userLang;
                if (document.cookie.indexOf(cookieName + '=' + cookieValue) === -1) {
                    document.cookie = cookieName + '=' + cookieValue + '; path=/';
                }
            }
        })();
    </script>

    <style>
        .goog-te-banner-frame.skiptranslate { display: none !important; } 
        body { top: 0px !important; }
        #google_translate_element { display: none !important; }
        .goog-tooltip { display: none !important; }
        .goog-tooltip:hover { display: none !important; }
        .goog-text-highlight { background-color: transparent !important; border: none !important; box-shadow: none !important; }

        body { font-family: Arial, sans-serif; background-color: #1e1e1e; color: #fff; margin: 0; padding: 40px 20px; }
        .container { width: 100%; max-width: 700px; margin: 0 auto; background-color: #2d2d2d; padding: 30px; box-sizing: border-box; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        h1 { color: #4CAF50; font-size: 24px; border-bottom: 1px solid #444; padding-bottom: 10px; margin-top: 0; }
        label { display: block; margin-top: 15px; font-weight: bold; color: #ddd; }
        select, input[type="text"] { width: 100%; padding: 10px; margin-top: 5px; border-radius: 5px; border: 1px solid #555; background: #444; color: white; font-size: 14px; box-sizing: border-box; }
        .btn-start { margin-top: 25px; background-color: #4CAF50; color: white; border: none; padding: 15px 20px; font-size: 18px; font-weight: bold; border-radius: 5px; cursor: pointer; width: 100%; transition: 0.3s; box-sizing: border-box; }
        .btn-start:hover { background-color: #45a049; }
        .btn-start:disabled { background-color: #555; cursor: not-allowed; color: #888; }
        
        .status-box { margin-top: 20px; padding: 15px; background: #111; border-radius: 5px; border-left: 4px solid #4CAF50; transition: 0.3s; }
        .status-title { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
        #status_text { font-family: monospace; font-size: 14px; color: #4CAF50; word-break: break-all; margin-bottom: 15px; }
        .current-item { color: #2196F3; font-weight: bold; font-family: monospace; font-size: 14px; margin-bottom: 15px; background: #222; padding: 8px; border-radius: 4px; word-break: break-all; }
        
        .lists-container { display: flex; gap: 15px; }
        .list-box { flex: 1; background: #1a1a1a; padding: 10px; border-radius: 5px; height: 150px; overflow-y: auto; border: 1px solid #333; }
        .list-box h4 { margin-top: 0; margin-bottom: 10px; font-size: 13px; color: #ccc; border-bottom: 1px solid #333; padding-bottom: 5px; }
        ul { list-style-type: none; padding: 0; margin: 0; font-size: 12px; font-family: monospace; }
        li { padding: 4px 0; border-bottom: 1px dashed #333; word-break: break-all; }
        .success-item { color: #4CAF50; }
        .error-item { color: #ff5252; }
        .note { font-size: 12px; color: #aaa; margin-top: 5px; }
        
        .folder-list { max-height: 250px; overflow-y: auto; background: #444; border: 1px solid #555; border-radius: 5px; padding: 15px; margin-top: 5px; }
        .folder-list details { margin-left: 20px; margin-bottom: 4px; }
        .folder-list summary { cursor: pointer; user-select: none; color: #ccc; font-weight: normal; font-size: 14px; word-break: break-word; }
        .folder-list summary:hover { color: #fff; }
        .folder-list input[type="checkbox"] { margin-right: 8px; cursor: pointer; flex-shrink: 0; }
        .leaf-folder { display: flex; align-items: flex-start; margin-left: 20px; margin-top: 4px; margin-bottom: 4px; color: #ccc; cursor: pointer; font-weight: normal; font-size: 14px; word-break: break-word; }
        .leaf-folder:hover { color: #fff; }
        .main-root-folder { display:flex; align-items: flex-start; margin-bottom: 15px; border-bottom: 1px solid #666; padding-bottom: 15px; cursor: pointer; font-size: 14px; }
        
        .coffee-container { text-align: center; margin-bottom: 20px; }
        .btn-coffee { display: inline-block; background-color: #FFDD00; color: #222; text-decoration: none; padding: 8px 16px; font-weight: bold; border-radius: 5px; transition: 0.3s; font-size: 13px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
        .btn-coffee:hover { background-color: #ffea00; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.3); }

        @media (max-width: 600px) {
            body { padding: 15px 10px; }
            .container { padding: 20px; }
            .lists-container { flex-direction: column; }
            .list-box { height: 120px; }
            h1 { font-size: 20px; }
            .btn-start { padding: 12px 15px; font-size: 16px; }
        }
    </style>
</head>
<body>
    <div id="google_translate_element"></div>
    <script type="text/javascript">
        function googleTranslateElementInit() {
            new google.translate.TranslateElement({pageLanguage: 'nl', autoDisplay: false}, 'google_translate_element');
        }
    </script>
    <script type="text/javascript" src="https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>

    <div class="container">
        <h1>Ultimate Video Converter</h1>
        
        <div class="coffee-container">
            <a href="https://www.paypal.com/paypalme/PandaBoyNL" target="_blank" class="btn-coffee">☕ Buy Me a Coffee (PayPal)</a>
        </div>

        <div class="status-box" id="status_box">
            <div class="status-title">Huidige Status</div>
            <div id="status_text">{{ state.status_text }}</div>
            
            <div class="status-title">▶ Nu bezig met:</div>
            <div id="current_file" class="current-item">-</div>

            <div class="lists-container">
                <div class="list-box">
                    <h4>✅ Succesvol Afgerond</h4>
                    <ul id="completed_list"></ul>
                </div>
                <div class="list-box">
                    <h4>❌ Mislukt / Fouten</h4>
                    <ul id="failed_list"></ul>
                </div>
            </div>
        </div>

        <form method="POST" id="convertForm">
            <label>1. Kies de mappen (klik op een mapnaam om uit te klappen):</label>
            <div class="folder-list">
                <label class="main-root-folder">
                    <input type="checkbox" name="target_folders" value="/"> 
                    <strong>/ (De complete hoofdmap converteren)</strong>
                </label>
                {% macro render_tree(tree, current_path="") %}
                    {% for name, sub_tree in tree.items() %}
                        {% set new_path = current_path + '/' + name if current_path else name %}
                        {% if sub_tree %}
                            <details>
                                <summary>
                                    <input type="checkbox" name="target_folders" value="{{ new_path }}" onclick="event.stopPropagation()">
                                    📁 {{ name }}
                                </summary>
                                {{ render_tree(sub_tree, new_path) }}
                            </details>
                        {% else %}
                            <label class="leaf-folder">
                                <input type="checkbox" name="target_folders" value="{{ new_path }}">
                                📂 {{ name }}
                            </label>
                        {% endif %}
                    {% endfor %}
                {% endmacro %}
                {{ render_tree(directories) }}
            </div>

            <label>2. Kies het Doel Formaat (Extensie):</label>
            <select name="target_ext">
                {% for f in formats %}
                    <option value="{{ f }}" {% if f == 'matroska' %}selected{% endif %}>{{ f | upper }}</option>
                {% endfor %}
            </select>

            <label>3. Video Codec:</label>
            <select name="vcodec">
                {% for vc in vcodecs %}
                    <option value="{{ vc }}" {% if vc == 'libx265' %}selected{% endif %}>{{ vc }}</option>
                {% endfor %}
            </select>
            
            <label>4. Audio Codec:</label>
            <select name="acodec">
                {% for ac in acodecs %}
                    <option value="{{ ac }}" {% if ac == 'copy' %}selected{% endif %}>{{ ac }}</option>
                {% endfor %}
            </select>

            <label>5. Discord Notificaties (Optioneel):</label>
            <input type="text" name="webhook_url" placeholder="https://discord.com/api/webhooks/..." value="{{ state.webhook_url }}">
            <div class="note">Je krijgt een berichtje zodra de complete wachtrij is afgerond. Je mag het venster veilig sluiten.</div>

            <button type="submit" class="btn-start" id="submit_btn">🚀 Start Conversie</button>
        </form>
    </div>

    <script>
        setInterval(() => {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    const statusText = document.getElementById('status_text');
                    const statusBox = document.getElementById('status_box');
                    statusText.innerText = data.status_text;
                    
                    if (data.status_text.includes("FOUT") || data.status_text.includes("Fout")) {
                        statusText.style.color = "#ff5252";
                        statusBox.style.borderLeft = "4px solid #ff5252";
                    } else if (data.status_text.includes("Waarschuwing")) {
                        statusText.style.color = "#ffb300";
                        statusBox.style.borderLeft = "4px solid #ffb300";
                    } else {
                        statusText.style.color = "#4CAF50";
                        statusBox.style.borderLeft = "4px solid #4CAF50";
                    }

                    document.getElementById('current_file').innerText = data.current_file || "-";

                    const compList = document.getElementById('completed_list');
                    compList.innerHTML = "";
                    data.completed_files.forEach(file => {
                        let li = document.createElement('li');
                        li.className = "success-item";
                        li.innerText = file;
                        compList.appendChild(li);
                    });

                    const failList = document.getElementById('failed_list');
                    failList.innerHTML = "";
                    data.failed_files.forEach(file => {
                        let li = document.createElement('li');
                        li.className = "error-item";
                        li.innerText = file;
                        failList.appendChild(li);
                    });

                    const btn = document.getElementById('submit_btn');
                    if (data.is_running) {
                        btn.disabled = true;
                        btn.innerText = "⏳ Conversie is bezig...";
                    } else {
                        btn.disabled = false;
                        btn.innerText = "🚀 Start Conversie";
                    }
                });
        }, 1000);
    </script>
</body>
</html>
"""

def converter_job(folders, target_format, vcodec, acodec, webhook_url):
    print(f"DEBUG: converter_job gestart met mappen: {folders} en webhook: {webhook_url}", flush=True)
    STATE["is_running"] = True
    STATE["completed_files"] = []
    STATE["failed_files"] = []
    STATE["current_file"] = "-"
    
    target_format = target_format.lower()
    final_ext = EXT_MAPPING.get(target_format, target_format)
    
    search_paths = []
    if "/" in folders:
        search_paths = [MEDIA_MAP]
    else:
        folders.sort()
        cleaned_folders = []
        for f in folders:
            if not any(f.startswith(cf + '/') for cf in cleaned_folders):
                cleaned_folders.append(f)
        search_paths = [os.path.join(MEDIA_MAP, f) for f in cleaned_folders]
    
    print(f"DEBUG: Zoekpaden vastgesteld op: {search_paths}", flush=True)

    test_file = os.path.join(MEDIA_MAP, ".test_write")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        print(f"DEBUG: Schrijfrechtenfout: {e}", flush=True)
        STATE["status_text"] = f"FOUT: De media map in Unraid staat op Read-Only of heeft geen schrijfrechten!"
        STATE["is_running"] = False
        send_discord_notification(webhook_url, "🚨 **Foutmelding:** De media map in Unraid staat op Read-Only of heeft geen schrijfrechten!")
        return
        
    processed_any = False

    try:
        for search_path in search_paths:
            if not os.path.exists(search_path):
                print(f"DEBUG: Pad bestaat niet: {search_path}", flush=True)
                continue
                
            for root, dirs, files in os.walk(search_path):
                for file in files:
                    ext = file.split('.')[-1].lower()
                    
                    if ext == 'tmp' or ext == final_ext:
                        continue 
                        
                    source_path = os.path.join(root, file)
                    filename_no_ext = '.'.join(file.split('.')[:-1])
                    cache_path = os.path.join(CACHE_MAP, f"{filename_no_ext}.{final_ext}.tmp")
                    target_path = os.path.join(root, f"{filename_no_ext}.{final_ext}")
                    
                    if os.path.exists(cache_path):
                        continue
                        
                    processed_any = True
                    STATE["status_text"] = f"Aan het converteren in: {os.path.basename(root)}"
                    STATE["current_file"] = file
                    print(f"DEBUG: Start conversie bestand: {source_path}", flush=True)
                    
                    cmd = ['ffmpeg', '-y', '-i', source_path, '-f', target_format, '-c:v', vcodec, '-c:a', acodec, cache_path]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode == 0:
                        print(f"DEBUG: Conversie gelukt, verplaatsen naar: {target_path}", flush=True)
                        STATE["status_text"] = "Verplaatsen naar mediamap..."
                        shutil.move(cache_path, target_path)
                        if source_path != target_path:
                            os.remove(source_path)
                        STATE["completed_files"].append(f"{file} ➔ {filename_no_ext}.{final_ext}")
                    else:
                        error_lines = result.stderr.strip().split('\n')
                        last_error = " | ".join(error_lines[-2:]) if len(error_lines) > 1 else (error_lines[-1] if error_lines else "Onbekende fout")
                        print(f"DEBUG: Conversie mislukt voor {file}: {last_error}", flush=True)
                        STATE["failed_files"].append(f"{file} ({last_error})")
                        if os.path.exists(cache_path):
                            os.remove(cache_path)
                    
                    STATE["current_file"] = "-"
                    
        if processed_any:
            STATE["status_text"] = f"Klaar! Alle geselecteerde mappen zijn verwerkt."
            msg = f"✅ **Conversie Afronding!**\nAlle geselecteerde video's zijn verwerkt.\n**Gelukt:** {len(STATE['completed_files'])} video's\n**Mislukt:** {len(STATE['failed_files'])} video's"
            send_discord_notification(webhook_url, msg)
        else:
            STATE["status_text"] = f"Klaar! Geen (nieuwe) video's gevonden om te converteren."
            print("DEBUG: Geen bestanden gevonden om te verwerken.", flush=True)
            send_discord_notification(webhook_url, "ℹ️ **Conversie Check:** Er zijn geen nieuwe video's gevonden om te converteren.")
            
    except Exception as e:
        print(f"DEBUG: Exception in converter_job: {e}", flush=True)
        STATE["status_text"] = f"Systeemfout opgetreden: {str(e)}"
        send_discord_notification(webhook_url, f"❌ **Kritieke Fout:** Systeemfout opgetreden tijdens conversie: `{str(e)}`")
        
    STATE["current_file"] = "-"
    STATE["is_running"] = False
    print("DEBUG: converter_job afgerond, is_running op False gezet.", flush=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        print("DEBUG: POST ontvangen op index", flush=True)
        if not STATE["is_running"]:
            target_folders = request.form.getlist("target_folders")
            webhook_url = request.form.get("webhook_url", "").strip()
            
            if not webhook_url:
                webhook_url = os.environ.get("DISCORD_WEBHOOK", "")
                
            STATE["webhook_url"] = webhook_url 
            
            if not target_folders:
                print("DEBUG: Geen mappen geselecteerd bij POST", flush=True)
                STATE["status_text"] = "Waarschuwing: Je hebt geen map geselecteerd!"
                return redirect(url_for('index'))
                
            target_ext = request.form.get("target_ext")
            vcodec = request.form.get("vcodec")
            acodec = request.form.get("acodec")
            
            print(f"DEBUG: Start thread met mappen: {target_folders}, ext: {target_ext}, vcodec: {vcodec}, acodec: {acodec}", flush=True)
            STATE["status_text"] = "Conversie wordt voorbereid..."
            
            thread = threading.Thread(target=converter_job, args=(target_folders, target_ext, vcodec, acodec, webhook_url))
            thread.daemon = True
            thread.start()
        else:
            print("DEBUG: Ontvangen POST genegeerd omdat is_running al True is!", flush=True)
            
        return redirect(url_for('index'))
            
    return render_template_string(HTML_TEMPLATE, 
                                  formats=ALL_FORMATS,
                                  vcodecs=ALL_VCODECS,
                                  acodecs=ALL_ACODECS,
                                  directories=get_directory_tree(),
                                  state=STATE)

@app.route('/api/status')
def status():
    return jsonify(STATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)