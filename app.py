from flask import Flask, render_template, send_file, request, abort, jsonify
import os
import subprocess
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

BASE_DIR = Path(__file__).parent.resolve()
IPAS_DIR = BASE_DIR / 'ipas'
CERTS_DIR = BASE_DIR / 'certs'
SIGNED_DIR = BASE_DIR / 'signed'
LOG_FILE = BASE_DIR / 'signing.log'
ZSIGN_BIN = BASE_DIR / 'bin' / 'zsign'

for d in [IPAS_DIR, CERTS_DIR, SIGNED_DIR]:
    d.mkdir(exist_ok=True)

def log(message):
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}\n"
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line)
        print(log_line.strip())
    except Exception:
        pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files')
def list_files():
    try:
        ipas = []
        if IPAS_DIR.exists():
            for f in IPAS_DIR.iterdir():
                if f.is_file() and f.suffix.lower() == '.ipa':
                    host = request.host_url.rstrip('/')
                    if host.startswith('http://'):
                        host = host.replace('http://', 'https://')
                    ipas.append({
                        'name': f.name,
                        'install_url': f"{host}/install/{f.name}",
                    })
        return jsonify({'ipas': ipas})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/install/<filename>')
def install_ipa(filename):
    if '..' in filename or not filename.lower().endswith('.ipa'):
        abort(403)
    
    filepath = IPAS_DIR / filename
    if not filepath.exists():
        abort(404)
    
    log(f"=== Signing Started: {filename} ===")
    
    p12_file = None
    mobileprovision_file = None
    if CERTS_DIR.exists():
        for f in CERTS_DIR.iterdir():
            if f.suffix.lower() == '.p12':
                p12_file = f
            elif f.suffix.lower() == '.mobileprovision':
                mobileprovision_file = f
    
    if not p12_file or not mobileprovision_file:
        log("ERROR: Certificate files not found")
        return jsonify({'error': 'Certificate files not found'}), 404
    
    log(f"Found cert: {p12_file.name}")
    log(f"Found profile: {mobileprovision_file.name}")
    
    signed_output = SIGNED_DIR / filename
    
    if not ZSIGN_BIN.exists():
        log(f"ERROR: zsign binary not found at {ZSIGN_BIN}")
        return jsonify({'error': 'zsign binary missing'}), 500
    
    # プロファイルと完全に一致させる Bundle ID
    TARGET_BUNDLE_ID = "jp.co.rakuten-sec.iSPEED.Pushnotification.widgetapp.widgetkitextension"
    log(f"Target Bundle ID: {TARGET_BUNDLE_ID}")
    
    cert_password = os.environ.get('CERT_PASSWORD', '')
    
    # -b オプションで Bundle ID を強制書き換え
    cmd = [
        str(ZSIGN_BIN),
        '-k', str(p12_file),
        '-m', str(mobileprovision_file),
        '-p', cert_password,
        '-b', TARGET_BUNDLE_ID,
        '-o', str(signed_output),
        str(filepath)
    ]
    
    log(f"Executing: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip(): log(f"zsign: {line}")
        if result.stderr:
            for line in result.stderr.split('\n'):
                if line.strip(): log(f"zsign err: {line}")
                
        if result.returncode == 0:
            log("SUCCESS: Signing completed.")
        else:
            log(f"FAILED: zsign exited with code {result.returncode}")
    
    except subprocess.TimeoutExpired:
        log("ERROR: Signing process timed out")
    except Exception as e:
        log(f"ERROR: {e}")

    host = request.host_url.rstrip('/')
    if host.startswith('http://'):
        host = host.replace('http://', 'https://')
    
    manifest_url = f"{host}/manifest/{filename}"
    
    return jsonify({
        'status': 'completed',
        'manifest_url': f"itms-services://?action=download-manifest&url={manifest_url}",
        'log_url': '/api/logs'
    })

@app.route('/manifest/<filename>')
def manifest(filename):
    if '..' in filename or not filename.lower().endswith('.ipa'):
        abort(403)
    
    host = request.host_url.rstrip('/')
    if host.startswith('http://'):
        host = host.replace('http://', 'https://')
    
    ipa_url = f"{host}/signed/{filename}"
    title = filename.replace('.ipa', '')
    # manifest.plist にも同じ ID を埋め込む
    bundle_id = "jp.co.rakuten-sec.iSPEED.Pushnotification.widgetapp.widgetkitextension"
    
    plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>items</key>
  <array>
    <dict>
      <key>assets</key>
      <array>
        <dict>
          <key>kind</key>
          <string>software-package</string>
          <key>url</key>
          <string>""" + ipa_url + """</string>
        </dict>
      </array>
      <key>metadata</key>
      <dict>
        <key>bundle-identifier</key>
        <string>""" + bundle_id + """</string>
        <key>bundle-version</key>
        <string>1.0</string>
        
