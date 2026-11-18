from flask import Flask, render_template, send_file, request, abort, jsonify, Response
import os
import subprocess
import plistlib
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = Path(__file__).parent.resolve()
IPAS_DIR = BASE_DIR / "ipas"
CERTS_DIR = BASE_DIR / "certs"
SIGNED_DIR = BASE_DIR / "signed"
LOG_FILE = BASE_DIR / "signing.log"
ZSIGN_BIN = BASE_DIR / "bin" / "zsign"
TARGET_BUNDLE_ID = "jp.co.rakuten-sec.iSPEED.Pushnotification.widgetapp.widgetkitextension"

for directory in (IPAS_DIR, CERTS_DIR, SIGNED_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    try:
        with LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(line)
    except OSError:
        pass
    print(line.rstrip())


def public_base_url():
    forwarded = request.headers.get("X-Forwarded-Proto", "")
    scheme = forwarded.split(",")[0].strip() if forwarded else request.scheme
    if scheme not in ("http", "https"):
        scheme = "https"
    return f"{scheme}://{request.host}"


def valid_ipa_name(filename):
    return (
        bool(filename)
        and filename == Path(filename).name
        and filename not in (".", "..")
        and filename.lower().endswith(".ipa")
        and secure_filename(filename) == filename
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/files")
def list_files():
    try:
        files = []
        for file in sorted(IPAS_DIR.iterdir()):
            if file.is_file() and file.suffix.lower() == ".ipa":
                files.append({
                    "name": file.name,
                    "install_url": f"{public_base_url()}/install/{file.name}",
                })
        return jsonify({"ipas": files})
    except Exception as error:
        log(f"ERROR listing IPA files: {error}")
        return jsonify({"error": "Unable to list IPA files"}), 500


@app.route("/api/logs")
def get_logs():
    try:
        if not LOG_FILE.exists():
            return jsonify({"logs": []})
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines(True)
        return jsonify({"logs": lines[-300:]})
    except OSError as error:
        return jsonify({"error": str(error), "logs": []}), 500


@app.route("/install/<filename>")
def install_ipa(filename):
    if not valid_ipa_name(filename):
        abort(403)

    ipa_path = IPAS_DIR / filename
    if not ipa_path.is_file():
        abort(404)

    log(f"=== Signing Started: {filename} ===")

    p12_file = next((p for p in CERTS_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".p12"), None)
    profile_file = next((p for p in CERTS_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".mobileprovision"), None)

    if not p12_file or not profile_file:
        log("ERROR: Certificate or provisioning profile not found")
        return jsonify({"error": "Certificate files not found"}), 404

    if not ZSIGN_BIN.is_file():
        log(f"ERROR: zsign binary not found at {ZSIGN_BIN}")
        return jsonify({"error": "zsign binary missing"}), 500

    output_path = SIGNED_DIR / filename
    password = os.environ.get("CERT_PASSWORD", "")

    command = [
        str(ZSIGN_BIN),
        "-k", str(p12_file),
        "-m", str(profile_file),
        "-p", password,
        "-b", TARGET_BUNDLE_ID,
        "-o", str(output_path),
        str(ipa_path),
    ]

    log(f"Using certificate: {p12_file.name}")
    log(f"Using profile: {profile_file.name}")
    log(f"Target Bundle ID: {TARGET_BUNDLE_ID}")
    log("Starting zsign")

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        for line in result.stdout.splitlines():
            if line.strip():
                log(f"zsign: {line}")
        for line in result.stderr.splitlines():
            if line.strip():
                log(f"zsign err: {line}")

        if result.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
            log(f"FAILED: zsign exit code {result.returncode}; output file missing or empty")
            return jsonify({
                "error": "Signing failed",
                "return_code": result.returncode,
                "log_url": "/api/logs",
            }), 500

    except subprocess.TimeoutExpired:
        log("ERROR: Signing process timed out")
        return jsonify({"error": "Signing timed out", "log_url": "/api/logs"}), 504
    except Exception as error:
        log(f"ERROR running zsign: {error}")
        return jsonify({"error": "Unable to run signing process", "log_url": "/api/logs"}), 500

    log(f"SUCCESS: Signing completed: {output_path.name}")
    manifest_url = f"{public_base_url()}/manifest/{filename}"
    return jsonify({
        "status": "completed",
        "manifest_url": f"itms-services://?action=download-manifest&url={manifest_url}",
        "log_url": "/api/logs",
    })


@app.route("/manifest/<filename>")
def manifest(filename):
    if not valid_ipa_name(filename):
        abort(403)

    signed_path = SIGNED_DIR / filename
    if not signed_path.is_file():
        abort(404)

    base_url = public_base_url()
    manifest_data = {
        "items": [{
            "assets": [{
                "kind": "software-package",
                "url": f"{base_url}/signed/{filename}",
            }],
            "metadata": {
                "bundle-identifier": TARGET_BUNDLE_ID,
                "bundle-version": "1.0",
                "kind": "software",
                "title": Path(filename).stem,
            },
        }]
    }

    response = Response(
        plistlib.dumps(manifest_data, fmt=plistlib.FMT_XML, sort_keys=False),
        mimetype="application/xml",
    )
    response.headers["Content-Disposition"] = 'attachment; filename="manifest.plist"'
    return response


@app.route("/signed/<filename>")
def download_signed_ipa(filename):
    if not valid_ipa_name(filename):
        abort(403)

    signed_path = SIGNED_DIR / filename
    if not signed_path.is_file():
        abort(404)

    return send_file(
        signed_path,
        mimetype="application/octet-stream",
        as_attachment=False,
        download_name=filename,
    )


if __name__ == "__main__":
    from werkzeug.serving import run_simple
    run_simple("0.0.0.0", int(os.environ.get("PORT", "10000")), app)
