import os
import plistlib
import zipfile
from flask import Flask, abort, redirect, send_from_directory, Response, url_for

app = Flask(__name__, static_folder=None)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://neveripa.onrender.com"


def ipa_exists(filename):
    return (
        filename.endswith(".ipa")
        and os.path.basename(filename) == filename
        and os.path.isfile(os.path.join(BASE_DIR, filename))
    )


def read_ipa_info(filename):
    path = os.path.join(BASE_DIR, filename)
    with zipfile.ZipFile(path, "r") as archive:
        info_path = next(
            (
                name for name in archive.namelist()
                if name.startswith("Payload/") and name.endswith(".app/Info.plist")
            ),
            None,
        )
        if not info_path:
            raise ValueError("Info.plist not found")

        info = plistlib.loads(archive.read(info_path))

    bundle_id = info.get("CFBundleIdentifier")
    if not bundle_id:
        raise ValueError("Bundle ID not found")

    return {
        "bundle_id": bundle_id,
        "version": str(info.get("CFBundleVersion", "1.0")),
        "title": info.get("CFBundleDisplayName")
        or info.get("CFBundleName")
        or filename[:-4],
    }


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/ipa/")
@app.get("/ipa")
def ipa_root():
    abort(404)


@app.get("/ipa/<path:filename>")
def serve_ipa(filename):
    filename = os.path.basename(filename)
    if not ipa_exists(filename):
        abort(404)
    return send_from_directory(
        BASE_DIR,
        filename,
        mimetype="application/octet-stream",
        as_attachment=False,
        download_name=filename,
    )


@app.get("/manifest/<path:filename>.plist")
def manifest(filename):
    filename = os.path.basename(filename)
    if not ipa_exists(filename):
        abort(404)

    try:
        info = read_ipa_info(filename)
    except (zipfile.BadZipFile, KeyError, ValueError, plistlib.InvalidFileException):
        abort(422)

    ipa_url = SITE_URL + url_for("serve_ipa", filename=filename)
    manifest_data = {
        "items": [{
            "assets": [{
                "kind": "software-package",
                "url": ipa_url,
            }],
            "metadata": {
                "bundle-identifier": info["bundle_id"],
                "bundle-version": info["version"],
                "kind": "software",
                "title": info["title"],
            },
        }]
    }

    return Response(
        plistlib.dumps(manifest_data, fmt=plistlib.FMT_XML),
        mimetype="application/xml",
    )


@app.get("/<path:filename>")
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
