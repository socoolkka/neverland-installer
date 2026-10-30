import os
import hmac
import plistlib
import subprocess
import zipfile
from pathlib import Path
from flask import Flask, abort, request, send_from_directory, Response, url_for

app = Flask(__name__, static_folder=None)
BASE_DIR = Path(__file__).resolve().parent
SITE_URL = "https://neveripa.onrender.com"
SIGNED_DIR = BASE_DIR / "signed"
ZSIGN = BASE_DIR / ".bin" / "zsign"


def configured_file(env_name, default_name):
    value = os.environ.get(env_name, default_name)
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


P12_PATH = configured_file("P12_PATH", "RAKUTEN SECURITIES,INC.p12")
PROFILE_PATH = configured_file("MOBILEPROVISION_PATH", "RAKUTEN SECURITIES,INC.mobileprovision")


def ipa_exists(filename):
    return filename.endswith(".ipa") and Path(filename).name == filename and (BASE_DIR / filename).is_file()


def read_ipa_info(path):
    with zipfile.ZipFile(path, "r") as archive:
        info_path = next((name for name in archive.namelist()
                          if name.startswith("Payload/") and name.endswith(".app/Info.plist")), None)
        if not info_path:
            raise ValueError("Info.plist not found")
        info = plistlib.loads(archive.read(info_path))
    bundle_id = info.get("CFBundleIdentifier")
    if not bundle_id:
        raise ValueError("Bundle ID not found")
    return {
        "bundle_id": bundle_id,
        "version": str(info.get("CFBundleVersion", "1.0")),
        "title": info.get("CFBundleDisplayName") or info.get("CFBundleName") or Path(path).stem,
    }


def authorized():
    expected = os.environ.get("SIGNING_TOKEN", "")
    supplied = request.headers.get("Authorization", "")
    if not expected or not hmac.compare_digest(supplied, "Bearer " + expected):
        abort(403)


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/ipa/")
@app.get("/ipa")
def ipa_root():
    abort(404)


@app.get("/ipa/<path:filename>")
def serve_ipa(filename):
    filename = Path(filename).name
    if not ipa_exists(filename):
        abort(404)
    return send_from_directory(BASE_DIR, filename, mimetype="application/octet-stream", as_attachment=False)


@app.post("/sign/<path:filename>")
def sign_ipa(filename):
    authorized()
    filename = Path(filename).name
    if not ipa_exists(filename):
        abort(404)

    password = os.environ.get("P12_PASSWORD", "")
    if not password:
        return {"error": "P12_PASSWORD is not configured"}, 503
    if not P12_PATH.is_file() or not PROFILE_PATH.is_file():
        return {"error": "P12_PATH or MOBILEPROVISION_PATH file is missing"}, 503
    if not ZSIGN.is_file():
        return {"error": "zsign binary is missing; check Render build command"}, 503

    SIGNED_DIR.mkdir(parents=True, exist_ok=True)
    output = SIGNED_DIR / (Path(filename).stem + "-signed.ipa")
    command = [str(ZSIGN), "-f", "-k", str(P12_PATH), "-p", password,
               "-m", str(PROFILE_PATH), "-o", str(output), str(BASE_DIR / filename)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
    except subprocess.TimeoutExpired:
        return {"error": "Signing timed out"}, 504

    if result.returncode != 0 or not output.is_file():
        return {"error": "Signing failed", "details": (result.stderr or result.stdout)[-3000:]}, 422

    return {
        "status": "signed",
        "filename": output.name,
        "download_url": SITE_URL + url_for("serve_signed", filename=output.name),
        "manifest_url": SITE_URL + url_for("signed_manifest", filename=output.name),
    }


@app.get("/signed/<path:filename>")
def serve_signed(filename):
    filename = Path(filename).name
    if not filename.endswith("-signed.ipa") or not (SIGNED_DIR / filename).is_file():
        abort(404)
    return send_from_directory(SIGNED_DIR, filename, mimetype="application/octet-stream", as_attachment=False)


@app.get("/manifest/<path:filename>.plist")
def manifest(filename):
    filename = Path(filename).name
    if not ipa_exists(filename):
        abort(404)
    return make_manifest(BASE_DIR / filename, "serve_ipa", filename)


@app.get("/manifest/signed/<path:filename>.plist")
def signed_manifest(filename):
    filename = Path(filename).name
    if not filename.endswith("-signed.ipa") or not (SIGNED_DIR / filename).is_file():
        abort(404)
    return make_manifest(SIGNED_DIR / filename, "serve_signed", filename)


def make_manifest(ipa_path, endpoint, filename):
    try:
        info = read_ipa_info(ipa_path)
    except (zipfile.BadZipFile, KeyError, ValueError, plistlib.InvalidFileException):
        abort(422)
    ipa_url = SITE_URL + url_for(endpoint, filename=filename)
    data = {"items": [{
        "assets": [{"kind": "software-package", "url": ipa_url}],
        "metadata": {
            "bundle-identifier": info["bundle_id"],
            "bundle-version": info["version"],
            "kind": "software",
            "title": info["title"],
        },
    }]}
    return Response(plistlib.dumps(data, fmt=plistlib.FMT_XML), mimetype="application/xml")


@app.get("/<path:filename>")
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
