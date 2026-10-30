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
                    ipas.append({
                        'name': f.name,
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
