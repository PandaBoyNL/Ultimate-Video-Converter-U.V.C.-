import os
import threading
import subprocess
import shutil
import time
import json
import urllib.request
import logging
from flask import Flask, request, render_template_string, jsonify, redirect, url_for

app = Flask(__name__)

# --- STOP DE LOG-SPAM VAN DE STATUS ---
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)
# -------------------------------------

# --- DYNAMISCHE FFMPEG PARSER & FORMATEN ---
def get_formatted_formats():
    try:
        result = subprocess.run(['ffmpeg', '-formats'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        raw_formats = set()
        for line in result.stdout.splitlines():
            if len(line) > 4 and line[2] == 'E':
                for fmt in line[4:].split()[0].split(','):
                    raw_formats.add(fmt.strip())
    except:
        raw_formats = {"matroska", "mp4", "avi", "mov", "webm", "ts"}

    priority = ["matroska", "mp4", "avi", "mov", "webm", "mpegts"]
    
    display_names = {
        "matroska": "MKV", "mp4": "MP4", "ipod": "MP4", "avi": "AVI",
        "mov": "MOV", "webm": "WEBM", "mpegts": "TS", "asf": "WMV", "flv": "FLV"
    }

    sorted_formats = [p for p in priority if p in raw_formats]
    raw_formats.difference_update(priority)
    sorted_formats.extend(sorted(list(raw_formats)))

    return [(fmt, display_names.get(fmt, fmt.upper())) for fmt in sorted_formats]

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

ALL_FORMATS = get_formatted_formats()
ALL_VCODECS = get_ffmpeg_codecs('V')
ALL_ACODECS = get_ffmpeg_codecs('A')

EXT_MAPPING = {"matroska": "mkv", "ipod": "mp4", "mpegts": "ts", "asf": "wmv"}

MEDIA_MAP = "/media"
CACHE_MAP = "/cache"

# VUL HIER JOUW DISCORD WEBHOOK IN VOOR DE SUPPORT POP-UP KNOP
SUPPORT_WEBHOOK = "https://discord.com/api/webhooks/1548761361469939802/NFyCL5Qmlt1J_mby3AtkcJQWi6T2nlTjqaZq8Eyi1nBKJZnLsuXaw5A3JMq4iYMqyF63"
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
    if not os.path.exists(path): return tree
    try:
        with os.scandir(path) as it:
            entries = sorted([entry for entry in it if entry.is_dir()], key=lambda e: e.name.lower())
            for entry in entries:
                tree[entry.name] = get_directory_tree(entry.path)
    except PermissionError:
        pass
    return tree

def send_discord_notification(webhook_url, message):
    if not webhook_url or not webhook_url.startswith("http"): return
    data = {
        "content": message,
        "username": "Ultimate Video Converter",
        "avatar_url": "https://raw.githubusercontent.com/PandaBoyNL/Ultimate-Video-Converter-U.V.C.-/main/logo.png"
    }
    headers = {'Content-Type': 'application/json', 'User-Agent': 'UltimateVideoConverter/1.0'}
    req = urllib.request.Request(webhook_url, data=json.dumps(data).encode('utf-8'), headers=headers)
    try:
        urllib.request.urlopen(req)
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
            if (document.cookie.indexOf('googtrans') === -1) {
                let userLang = navigator.language || navigator.userLanguage;
                let shortLang = userLang.split('-')[0].toLowerCase();
                if (userLang.toLowerCase() === 'zh-cn' || userLang.toLowerCase() === 'zh-tw') shortLang = 'zh-CN';
                const ondersteundeTalen = ['en', 'de', 'fr', 'es', 'it', 'pt', 'pl', 'ru', 'tr', 'ar', 'zh-CN', 'ja', 'ko', 'hi'];
                if (ondersteundeTalen.includes(shortLang) && shortLang !== 'nl') {
                    document.cookie = 'googtrans=/nl/' + shortLang + '; path=/';
                }
            }
        })();
    </script>

    <style>
        /* Voorkom dat de vertaalbalk de layout naar beneden verschuift */
        body { top: 0px !important; position: static !important; }

        /* Verberg alle varianten van Google's bovenbalk en iframes */
        iframe.skiptranslate,
        .goog-te-banner-frame,
        .goog-te-banner-frame.skiptranslate,
        .VIpgJd-ZVi9I-OR9ErZ-OEVmcd { 
            display: none !important; 
            visibility: hidden !important; 
        }

        /* Verberg hover pop-ups, tekstballonnen en markeringen */
        #goog-gt-tt,
        .goog-te-balloon-frame { 
            display: none !important; 
        }

        .goog-text-highlight { 
            background-color: transparent !important; 
            box-shadow: none !important; 
            border: none !important; 
        }

        #google_translate_element { 
            display: none !important; 
        }

        body { font-family: Arial, sans-serif; background-color: #1e1e1e; color: #fff; margin: 0; padding: 40px 20px; }
        .container { width: 100%; max-width: 700px; margin: 0 auto; background-color: #2d2d2d; padding: 30px; box-sizing: border-box; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        h1 { color: #4CAF50; font-size: 24px; border-bottom: 1px solid #444; padding-bottom: 10px; margin-top: 0; }
        label { display: block; margin-top: 15px; font-weight: bold; color: #ddd; }
        select, input[type="text"] { width: 100%; padding: 10px; margin-top: 5px; border-radius: 5px; border: 1px solid #555; background: #444; color: white; font-size: 14px; box-sizing: border-box; }
        .checkbox-label { display: flex; align-items: center; margin-top: 15px; font-weight: normal; color: #ffb300; cursor: pointer; background: #222; padding: 10px; border-radius: 5px; border: 1px dashed #ffb300; }
        .checkbox-label input { width: 18px; height: 18px; margin-right: 10px; cursor: pointer; }
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
        .leaf-folder, .main-root-folder { display: flex; align-items: flex-start; margin-left: 20px; margin-top: 4px; margin-bottom: 4px; color: #ccc; cursor: pointer; font-weight: normal; font-size: 14px; word-break: break-word; }
        .leaf-folder:hover { color: #fff; }
        .main-root-folder { margin-left: 0; margin-bottom: 15px; border-bottom: 1px solid #666; padding-bottom: 15px; }
        
        .top-buttons { text-align: center; margin-bottom: 20px; display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; align-items: center; }
        .btn-coffee, .btn-discord, .lang-btn { display: inline-block; padding: 8px 16px; font-weight: bold; border-radius: 5px; transition: 0.3s; font-size: 13px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); text-decoration: none; cursor: pointer; border: none; }
        .btn-coffee { background-color: #FFDD00; color: #222; }
        .btn-coffee:hover { background-color: #ffea00; transform: translateY(-2px); }
        .btn-discord { background-color: #5865F2; color: #fff; }
        .btn-discord:hover { background-color: #4752c4; transform: translateY(-2px); }

        /* Vertaal Menu Dropdown - Naadloos aangesloten met hover-brug */
        .lang-menu { position: relative; display: inline-block; cursor: pointer; }
        .lang-btn { background: #333; color: #fff; font-size: 16px; padding: 7px 12px; }
        .lang-btn:hover { background: #444; transform: translateY(-2px); }
        
        .lang-dropdown { 
            display: none; 
            position: absolute; 
            right: 0; 
            top: 100%; 
            margin-top: 0px; 
            background: #2d2d2d; 
            min-width: 180px; 
            max-height: 350px; 
            overflow-y: auto; 
            box-shadow: 0 8px 25px rgba(0,0,0,0.7); 
            z-index: 100; 
            border-radius: 8px; 
            border: 1px solid #444; 
        }
        
        /* Onzichtbare brug boven de dropdown om wegvallen te voorkomen */
        .lang-dropdown::before {
            content: "";
            position: absolute;
            top: -10px;
            left: 0;
            width: 100%;
            height: 10px;
        }

        .lang-menu:hover .lang-dropdown { display: block; }
        .lang-dropdown a { color: #fff; padding: 10px 15px; text-decoration: none; display: block; font-size: 13px; transition: background 0.2s; font-weight: normal; text-align: left; }
        .lang-dropdown a:hover { background: #4CAF50; color: white; }

        /* MODAL CSS */
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.7); }
        .modal-content { background-color: #2d2d2d; margin: 10% auto; padding: 25px; border: 1px solid #444; width: 90%; max-width: 500px; border-radius: 10px; position: relative; box-shadow: 0 5px 15px rgba(0,0,0,0.5); }
        .close-btn { color: #aaa; position: absolute; top: 15px; right: 20px; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close-btn:hover { color: #fff; }
        .modal-content h2 { margin-top: 0; color: #5865F2; font-size: 22px; }
        .modal-content p { font-size: 14px; color: #ccc; margin-bottom: 15px; line-height: 1.4; }
        #supportMessage { width: 100%; padding: 12px; border-radius: 5px; border: 1px solid #555; background: #111; color: white; margin-bottom: 15px; resize: vertical; box-sizing: border-box; font-family: Arial; }
        
        @media (max-width: 600px) {
            body { padding: 15px 10px; }
            .container { padding: 20px; }
            .lists-container { flex-direction: column; }
            .list-box { height: 120px; }
            h1 { font-size: 20px; }
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

    <!-- Support Modal -->
    <div id="supportModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeSupportModal()">&times;</span>
            <h2>💬 Support & Feedback</h2>
            <p>Heb je een vraag, een bug gevonden of een verzoek voor een nieuwe functie? Stuur direct een bericht naar de ontwikkelaar (PandaBoyNL)!</p>
            <textarea id="supportMessage" rows="5" placeholder="Typ hier je bericht of vraag..."></textarea>
            <button class="btn-start" style="margin-top: 0; background-color: #5865F2;" onclick="sendSupportMessage()" id="btnSendSupport">Verstuur Bericht</button>
            <div id="supportStatus" style="margin-top: 15px; font-size: 14px; font-weight: bold; text-align: center;"></div>
        </div>
    </div>

    <div class="container">
        <h1>Ultimate Video Converter</h1>
        
        <div class="top-buttons">
            <button onclick="openSupportModal()" class="btn-discord">💬 Support & Contact</button>
            <a href="https://www.paypal.com/paypalme/PandaBoyNL" target="_blank" class="btn-coffee">☕ Buy Me a Coffee (PayPal)</a>
            
            <div class="lang-menu">
                <button class="lang-btn" title="Kies taal / Change language">🌍</button>
                <div class="lang-dropdown" id="lang-lijst"></div>
            </div>
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
            <label>1. Kies de mappen:</label>
            <div class="folder-list">
                <label class="main-root-folder">
                    <input type="checkbox" name="target_folders" value="/"> 
                    <strong>/ (De complete hoofdmap converteren)</strong>
                </label>
                {% macro render_tree(tree, current_path="") %}
                    {% for name, sub_tree in tree.items() %}
                        {% set new_path = current_path + '/' + name if current_path else name %}
                        {% if sub_tree %}
                            <details><summary><input type="checkbox" name="target_folders" value="{{ new_path }}" onclick="event.stopPropagation()"> 📁 {{ name }}</summary>{{ render_tree(sub_tree, new_path) }}</details>
                        {% else %}
                            <label class="leaf-folder"><input type="checkbox" name="target_folders" value="{{ new_path }}"> 📂 {{ name }}</label>
                        {% endif %}
                    {% endfor %}
                {% endmacro %}
                {{ render_tree(directories) }}
            </div>

            <label>2. Kies het Doel Formaat (Extensie):</label>
            <select name="target_ext">
                {% for val, label in formats %}<option value="{{ val }}" {% if val == 'matroska' %}selected{% endif %}>{{ label }}</option>{% endfor %}
            </select>

            <label>3. Video Codec:</label>
            <select name="vcodec">
                {% for vc in vcodecs %}<option value="{{ vc }}" {% if vc == 'copy' %}selected{% endif %}>{{ vc }}</option>{% endfor %}
            </select>
            
            <label>4. Audio Codec:</label>
            <select name="acodec">
                {% for ac in acodecs %}<option value="{{ ac }}" {% if ac == 'copy' %}selected{% endif %}>{{ ac }}</option>{% endfor %}
            </select>

            <!-- REPARATIE OPTIE -->
            <label class="checkbox-label">
                <input type="checkbox" name="repair_mode" value="yes"> 
                🛠️ <strong>Repareer beschadigde bestanden / Negeer stream-fouten (Corrupte index/headers herstellen)</strong>
            </label>

            <label>5. Jouw Discord Webhook (Optioneel, voor conversie-meldingen):</label>
            <input type="text" name="webhook_url" placeholder="https://discord.com/api/webhooks/..." value="{{ state.webhook_url }}">
            <div class="note">Je krijgt een berichtje zodra jouw eigen wachtrij is afgerond.</div>

            <button type="submit" class="btn-start" id="submit_btn">🚀 Start Conversie & Herstel</button>
        </form>
    </div>

    <script>
        // --- TALEN MENU VULLEN & SLIMME STATUS VERTALING ---
        const talen = { 
            "nl": "🇳🇱 Nederlands", "en": "🇺🇸 English", "de": "🇩🇪 Deutsch", 
            "fr": "🇫🇷 Français", "es": "🇪🇸 Español", "it": "🇮🇹 Italiano", 
            "pt": "🇵🇹 Português", "pl": "🇵🇱 Polski", "ru": "🇷🇺 Русский", 
            "tr": "🇹🇷 Türkçe", "ar": "🇸🇦 العربية", "zh-CN": "🇨🇳 中文", 
            "ja": "🇯🇵 日本語", "ko": "🇰🇷 한국어", "hi": "🇮🇳 हिन्दी" 
        };

        function getCurrentLang() {
            let match = document.cookie.match(/googtrans=\/nl\/([a-zA-Z\-]+)/);
            return match ? match[1] : 'nl';
        }

        function translateStatusText(text) {
            let lang = getCurrentLang();
            if (lang === 'nl') return text;

            if (lang === 'en') {
                if (text.includes("Klaar voor een nieuwe taak")) return "Ready for a new task. Select your folders and click Start.";
                if (text.includes("Conversie wordt voorbereid") || text.includes("Taak wordt voorbereid")) return "Preparing conversion...";
                if (text.startsWith("Aan het converteren/repareren in:")) {
                    let folder = text.replace("Aan het converteren/repareren in:", "").trim();
                    return "Converting/repairing in: " + folder;
                }
                if (text === "Verplaatsen naar mediamap...") return "Moving to media folder...";
                if (text.includes("Klaar! Alle geselecteerde mappen zijn verwerkt")) return "Done! All selected folders have been processed.";
                if (text.includes("Geen (nieuwe) video's gevonden")) return "Done! No (new) videos found to convert.";
                if (text.startsWith("FOUT:")) return text.replace("FOUT:", "ERROR:");
                if (text.startsWith("Systeemfout")) return text.replace("Systeemfout opgetreden:", "System error occurred:");
            }
            return text;
        }

        function laadTalenMenu() {
            const lijst = document.getElementById('lang-lijst');
            if (!lijst) return;
            lijst.innerHTML = '';
            for (const [code, naam] of Object.entries(talen)) {
                const a = document.createElement('a');
                a.href = "#";
                a.innerText = naam;
                a.onclick = (e) => {
                    e.preventDefault();
                    document.cookie = `googtrans=/nl/${code}; path=/`;
                    window.location.reload();
                };
                lijst.appendChild(a);
            }
        }
        laadTalenMenu();

        // Modal Functies
        function openSupportModal() {
            document.getElementById('supportModal').style.display = 'block';
            document.getElementById('supportStatus').innerText = '';
            document.getElementById('supportMessage').value = '';
        }

        function closeSupportModal() {
            document.getElementById('supportModal').style.display = 'none';
        }

        function sendSupportMessage() {
            const msg = document.getElementById('supportMessage').value;
            const status = document.getElementById('supportStatus');
            const btn = document.getElementById('btnSendSupport');
            
            if(!msg.trim()) {
                status.innerText = '❌ Typ eerst een bericht voordat je verzendt.';
                status.style.color = '#ff5252';
                return;
            }
            
            btn.disabled = true;
            status.innerText = '⏳ Bezig met versturen...';
            status.style.color = '#ffb300';
            
            fetch('/api/support', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: msg})
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    status.innerText = '✅ Bericht succesvol verstuurd!';
                    status.style.color = '#4CAF50';
                    setTimeout(closeSupportModal, 2500);
                } else {
                    status.innerText = '❌ Fout: ' + (data.error || 'Onbekende fout');
                    status.style.color = '#ff5252';
                }
            })
            .catch(err => {
                status.innerText = '❌ Netwerkfout. Probeer het later opnieuw.';
                status.style.color = '#ff5252';
            })
            .finally(() => {
                btn.disabled = false;
            });
        }

        window.onclick = function(event) {
            if (event.target == document.getElementById('supportModal')) {
                closeSupportModal();
            }
        }

        // Conversie Status Update met automatische taalaanpassing
        setInterval(() => {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    const statusText = document.getElementById('status_text');
                    const statusBox = document.getElementById('status_box');
                    
                    let vertaaldeStatus = translateStatusText(data.status_text);
                    statusText.innerText = vertaaldeStatus;
                    
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
                        let li = document.createElement('li'); li.className = "success-item"; li.innerText = file; compList.appendChild(li);
                    });

                    const failList = document.getElementById('failed_list');
                    failList.innerHTML = "";
                    data.failed_files.forEach(file => {
                        let li = document.createElement('li'); li.className = "error-item"; li.innerText = file; failList.appendChild(li);
                    });

                    const btn = document.getElementById('submit_btn');
                    let lang = getCurrentLang();
                    if (data.is_running) {
                        btn.disabled = true;
                        btn.innerText = (lang === 'en') ? "⏳ Converting & repairing..." : "⏳ Conversie & herstel bezig...";
                    } else {
                        btn.disabled = false;
                        btn.innerText = (lang === 'en') ? "🚀 Start Conversion & Repair" : "🚀 Start Conversie & Herstel";
                    }
                });
        }, 1000);
    </script>
</body>
</html>
"""

def converter_job(folders, target_format, vcodec, acodec, webhook_url, repair_mode):
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
    
    test_file = os.path.join(MEDIA_MAP, ".test_write")
    try:
        with open(test_file, 'w') as f: f.write("test")
        os.remove(test_file)
    except Exception:
        STATE["status_text"] = f"FOUT: De media map in Unraid staat op Read-Only of heeft geen schrijfrechten!"
        STATE["is_running"] = False
        send_discord_notification(webhook_url, "🚨 **Foutmelding:** De media map in Unraid staat op Read-Only of heeft geen schrijfrechten!")
        return
        
    processed_any = False
    
    # NIEUW: Definieer de toegestane video-extensies
    VALID_VIDEO_EXT = {'mkv', 'mp4', 'avi', 'mov', 'webm', 'ts', 'wmv', 'flv', 'm4v', 'mpg', 'mpeg', 'asf'}

    try:
        for search_path in search_paths:
            if not os.path.exists(search_path): continue
                
            for root, dirs, files in os.walk(search_path):
                for file in files:
                    ext = file.split('.')[-1].lower()
                    
                    # AANGEPAST: Sla tmp-bestanden, reeds geconverteerde bestanden én niet-videobestanden over
                    if ext == 'tmp' or ext == final_ext or ext not in VALID_VIDEO_EXT: continue 
                        
                    source_path = os.path.join(root, file)
                    filename_no_ext = '.'.join(file.split('.')[:-1])
                    cache_path = os.path.join(CACHE_MAP, f"{filename_no_ext}.{final_ext}.tmp")
                    target_path = os.path.join(root, f"{filename_no_ext}.{final_ext}")
                    
                    if os.path.exists(cache_path): continue
                        
                    processed_any = True
                    STATE["status_text"] = f"Aan het converteren/repareren in: {os.path.basename(root)}"
                    STATE["current_file"] = file
                    
                    cmd = ['ffmpeg', '-y']
                    if repair_mode:
                        cmd.extend(['-err_detect', 'ignore_err', '-fflags', '+genpts'])
                    cmd.extend(['-i', source_path, '-f', target_format, '-c:v', vcodec, '-c:a', acodec, cache_path])
                    
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode == 0:
                        STATE["status_text"] = "Verplaatsen naar mediamap..."
                        shutil.move(cache_path, target_path)
                        if source_path != target_path: os.remove(source_path)
                        STATE["completed_files"].append(f"{file} ➔ {filename_no_ext}.{final_ext}")
                    else:
                        error_lines = result.stderr.strip().split('\n')
                        last_error = " | ".join(error_lines[-2:]) if len(error_lines) > 1 else (error_lines[-1] if error_lines else "Onbekende fout")
                        STATE["failed_files"].append(f"{file} ({last_error})")
                        if os.path.exists(cache_path): os.remove(cache_path)
                    
                    STATE["current_file"] = "-"
                    
        if processed_any:
            STATE["status_text"] = f"Klaar! Alle geselecteerde mappen zijn verwerkt."
            msg = f"✅ **Conversie & Herstel Afronding!**\nAlle geselecteerde video's zijn verwerkt.\n**Gelukt:** {len(STATE['completed_files'])} video's\n**Mislukt:** {len(STATE['failed_files'])} video's"
            send_discord_notification(webhook_url, msg)
        else:
            STATE["status_text"] = f"Klaar! Geen (nieuwe) video's gevonden om te converteren."
            send_discord_notification(webhook_url, "ℹ️ **Conversie Check:** Er zijn geen nieuwe video's gevonden om te converteren.")
            
    except Exception as e:
        STATE["status_text"] = f"Systeemfout opgetreden: {str(e)}"
        send_discord_notification(webhook_url, f"❌ **Kritieke Fout:** Systeemfout opgetreden tijdens conversie: `{str(e)}`")
        
    STATE["current_file"] = "-"
    STATE["is_running"] = False

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if not STATE["is_running"]:
            target_folders = request.form.getlist("target_folders")
            webhook_url = request.form.get("webhook_url", "").strip()
            
            if not webhook_url: webhook_url = os.environ.get("DISCORD_WEBHOOK", "")
            STATE["webhook_url"] = webhook_url 
            
            if not target_folders:
                STATE["status_text"] = "Waarschuwing: Je hebt geen map geselecteerd!"
                return redirect(url_for('index'))
                
            target_ext = request.form.get("target_ext")
            vcodec = request.form.get("vcodec")
            acodec = request.form.get("acodec")
            repair_mode = True if request.form.get("repair_mode") == "yes" else False
            
            STATE["status_text"] = "Conversie wordt voorbereid..."
            thread = threading.Thread(target=converter_job, args=(target_folders, target_ext, vcodec, acodec, webhook_url, repair_mode))
            thread.daemon = True
            thread.start()
        return redirect(url_for('index'))
            
    return render_template_string(HTML_TEMPLATE, formats=ALL_FORMATS, vcodecs=ALL_VCODECS, acodecs=ALL_ACODECS, directories=get_directory_tree(), state=STATE)

@app.route('/api/status')
def status():
    return jsonify(STATE)

@app.route('/api/support', methods=['POST'])
def handle_support():
    data = request.json
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({"success": False, "error": "Bericht is leeg"}), 400
        
    if not SUPPORT_WEBHOOK or not SUPPORT_WEBHOOK.startswith("http"):
        return jsonify({"success": False, "error": "Ontwikkelaar heeft geen correcte webhook ingesteld"}), 500
        
    formatted_message = f"📩 **Nieuw Support Bericht via U.V.C. App:**\n```\n{message}\n```"
    send_discord_notification(SUPPORT_WEBHOOK, formatted_message)
    
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)