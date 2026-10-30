from flask import Flask, render_template, send_file, request, abort, jsonify
import os
import subprocess
import zipfile
import plistlib
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

BASE_DIR = Path(__file__).parent.resolve()
IPAS_DIR = BASE_DIR / 'ipas'
CERTS_DIR = BASE_DIR / 'certs'
SIGNED_DIR = BASE_DIR / 'signed'
LOG_FILE = BASE_DIR / 'signing.log'
ZSIGN_BIN = BASE_DIR / 'bin' / 'zsign'

# ディレクトリ作成
IPAS_DIR.mkdir(exist_ok=True)
CERTS_DIR.mkdir(exist_ok=True)
SIGNED_DIR.mkdir(exist_ok=True)

def log(message):
    """ログファイルに追記"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(log_line)
    print(log_line.strip())

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
                        'log_url': f"/api/logs"
                    })
        
        return jsonify({'ipas': ipas})
    except Exception as e:
        log(f"API ERROR: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/install/<filename>')
def install_ipa(filename):
    """署名処理を実行し、署名済みIPAを生成"""
    if '..' in filename or not filename.lower().endswith('.ipa'):
        abort(403)
    
    filepath = IPAS_DIR / filename
    if not filepath.exists():
        abort(404)
    
    # 証明書ファイルを探す
    p12_file = None
    mobileprovision_file = None
    if CERTS_DIR.exists():
        for f in CERTS_DIR.iterdir():
            if f.suffix.lower() == '.p12':
                p12_file = f
            elif f.suffix.lower() == '.mobileprovision':
                mobilepro
