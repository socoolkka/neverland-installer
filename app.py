from flask import Flask, render_template, send_file, request, abort, jsonify
import os
import subprocess
import zipfile
import plistlib
from pathlib import Path

app = Flask(__name__)

BASE_DIR = Path(__file__).parent.resolve()
IPAS_DIR = BASE_DIR / 'ipas'
CERTS_DIR = BASE_DIR / 'certs'
ZSIGN_PATH = BASE_DIR / 'zsign' / 'zsign'

IPAS_DIR.mkdir(exist_ok=True)
CERTS_DIR.mkdir(exist_ok=True)

P12_PASSWORD = os.environ.get('P12_PASSWORD', '')

def get_bundle_id_from_ipa(ipa_path):
    try:
        with zipfile.ZipFile(ipa_path, 'r') as zip_ref:
            for name in zip_ref.namelist():
                if name.endswith('.app/Info.plist'):
                    with zip_ref.open(name) as plist_file:
                        plist_data = plistlib.load(plist_file)
                        return plist_data.get('CFBundleIdentifier', 'lol.neverland.buttonapp')
    except Exception:
        pass
    return 'lol.neverland.buttonapp'

def sign_ipa(input_path, output_path):
    """zsignを使用してIPAに署名する"""
    if not ZSIGN_PATH.exists():
        print("ERROR: zsign not found. Build failed?")
        return False

    p12_file = None
    prov_file = None
    for f in CERTS_DIR.iterdir():
        if f.suffix.lower() == '.p12':
            p12_file = str(f)
        elif f.suffix.lower() == '.mobileprovision':
            prov_file = str(f)

    if not p12_file or not prov_file:
        print("ERROR: Missing .p12 or .mobileprovision in certs dir")
        return False

    cmd = [
        str(ZSIGN_PATH),
        '-k', p12_file,
        '-p', P12_PASSWORD,
        '-m', prov_file,
        '-o', str(output_path),
        str(input_path)
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Signing successful")
        return True
    else:
        print(f"Signing failed: {result.stderr}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files')
def list_files():
    try:
        ipas = []
        if IPAS_DIR.exists():
            for f in IPAS_DIR.iterdir():
                if f.is_file() and f.suffix.lower() == '.ipa' and not f.name.startswith('signed_'):
                    host = request.host_url.rstrip('/')
                    if host.startswith('http://'):
                        host = host.replace('http://', 'https://')
                    
                    ipas.append({
                        'name': f.name,
                        'install_url': f"itms-services://?action=download-manifest&url={host}/manifest/{f.name}",
                        'download_url': f"/api/{f.name}"
                    })
        return jsonify({'ipas': ipas})
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

@app.route('/manifest/<filename>')
def manifest(filename):
    if '..' in filename or not filename.lower().endswith('.ipa'):
        abort(403)
    
    input_filepath = IPAS_DIR / filename
    if not input_filepath.exists():
        abort(404)
    
    # 署名済みファイルの名前
    signed_filename = f"signed_{filename}"
    output_filepath = IPAS_DIR / signed_filename
    
    # 署名済みファイルがなければ生成
    if not output_filepath.exists():
        print(f"Signing {filename}...")
        success = sign_ipa(input_filepath, output_filepath)
        if not success:
            return jsonify({'error': 'Signing failed. Check P12_PASSWORD and certs.'}), 500
    
    bundle_id = get_bundle_id_from_ipa(output_filepath)
    
    host = request.host_url.rstrip('/')
    if host.startswith('http://'):
        host = host.replace('http://', 'https://')
        
    # manifestは署名済みIPAを指す
    ipa_url = f"{host}/api/{signed_filename}"
    title = filename.replace('.ipa', '')
    
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
        <key>kind</key>
        <string>software</string>
        <key>title</key>
        <string>""" + title + """</string>
      </dict>
    </dict>
  </array>
</dict>
</plist>"""
    
    return plist_content, 200, {'Content-Type': 'application/xml; charset=utf-8'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
