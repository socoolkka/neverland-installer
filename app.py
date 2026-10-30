from flask import Flask, render_template, send_file, request, abort, jsonify
import os
from pathlib import Path
import zipfile
import plistlib

app = Flask(__name__)

BASE_DIR = Path(__file__).parent.resolve()
IPAS_DIR = BASE_DIR / 'ipas'
CERTS_DIR = BASE_DIR / 'certs'

IPAS_DIR.mkdir(exist_ok=True)
CERTS_DIR.mkdir(exist_ok=True)

def get_bundle_id_from_ipa(ipa_path):
    """IPAからBundle IDを抽出"""
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            for name in z.namelist():
                if name.endswith('.app/Info.plist'):
                    with z.open(name) as f:
                        plist = plistlib.load(f)
                        return plist.get('CFBundleIdentifier', 'com.example.app')
    except Exception:
        pass
    return 'com.example.app'

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
                    
                    bundle_id = get_bundle_id_from_ipa(f)
                    
                    ipas.append({
                        'name': f.name,
                        'bundle_id': bundle_id,
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
    
    filepath = IPAS_DIR / filename
    if not filepath.exists():
        abort(404)
    
    bundle_id = get_bundle_id_from_ipa(filepath)
    title = filename.replace('.ipa', '')
    
    host = request.host_url.rstrip('/')
    if host.startswith('http://'):
        host = host.replace('http://', 'https://')
        
    ipa_url = f"{host}/api/{filename}"
    
    plist_dict = {
        'items': [{
            'assets': [{
                'kind': 'software-package',
                'url': ipa_url
            }],
            'metadata': {
                'bundle-identifier': bundle_id,
                'bundle-version': '1.0',
                'kind': 'software',
                'title': title
            }
        }]
    }
    
    plist_data = plistlib.dumps(plist_dict)
    return plist_data, 200, {'Content-Type': 'application/xml; charset=utf-8'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
