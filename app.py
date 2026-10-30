from flask import Flask, render_template, send_file, request, abort, jsonify
import os
from pathlib import Path

app = Flask(__name__)

BASE_DIR = Path(__file__).parent.resolve()
IPAS_DIR = BASE_DIR / 'ipas'
CERTS_DIR = BASE_DIR / 'certs'

IPAS_DIR.mkdir(exist_ok=True)
CERTS_DIR.mkdir(exist_ok=True)

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
                    # HTTPSを強制してOTAインストールリンクを生成
                    host = request.host_url.rstrip('/')
                    if host.startswith('http://'):
                        host = host.replace('http://', 'https://')
                    
                    ipas.append({
                        'name': f.name,
                        'install_url': f"itms-services://?action=download-manifest&url={host}/manifest/{f.name}",
                        'download_url': f"/api/{f.name}"
                    })
        
        certs = []
        if CERTS_DIR.exists():
            for f in CERTS_DIR.iterdir():
                if f.is_file() and f.suffix.lower() in ['.p12', '.mobileprovision']:
                    certs.append({
                        'name': f.name,
                        'download_url': f"/api/cert/{f.name}"
                    })
                    
        return jsonify({'ipas': ipas, 'certs': certs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/<filename>')
def serve_ipa(filename):
    if '..' in filename or not filename.lower().endswith('.ipa'):
        abort(403)
    filepath = IPAS_DIR / filename
    if not filepath.exists():
        abort(404)
    return send_file(filepath, as_attachment=True)

@app.route('/api/cert/<filename>')
def serve_cert(filename):
    if '..' in filename or not (filename.lower().endswith('.p12') or filename.lower().endswith('.mobileprovision')):
        abort(403)
    filepath = CERTS_DIR / filename
    if not filepath.exists():
        abort(404)
    return send_file(filepath, as_attachment=True)

@app.route('/manifest/<filename>')
def manifest(filename):
    if '..' in filename or not filename.lower().endswith('.ipa'):
        abort(403)
    
    host = request.host_url.rstrip('/')
    if host.startswith('http://'):
        host = host.replace('http://', 'https://')
        
    ipa_url = f"{host}/api/{filename}"
    title = filename.replace('.ipa', '')
    
    plist = f'''<?xml version="1.0" encoding="UTF-8"?>
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
          <string>{ipa_url}</string>
        </dict>
      </array>
      <key>metadata</key>
      <dict>
        <key>bundle-identifier</key>
        <string>com.example.app</string>
        <key>bundle-version</key>
        <string>1.0</string>
        <key>kind</key>
        <string>software</string>
        <key>title</key>
        <string>{title}</string>
      </dict>
    </dict>
  </array>
</dict>
</plist>'''
    # Content-Type を厳密に指定
    return plist, 200, {'Content-Type': 'application/xml; charset=utf-8'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
