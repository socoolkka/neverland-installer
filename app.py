import os
import html
import plistlib
import zipfile
from urllib.parse import quote
from flask import Flask, abort, redirect, send_from_directory, Response, url_for

app = Flask(__name__, static_folder=None)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://neveripa.onrender.com"

def get_ipa_files():
    return sorted(name for name in os.listdir(BASE_DIR)
                  if name.lower().endswith(".ipa") and os.path.isfile(os.path.join(BASE_DIR, name)))

def read_ipa_info(filename):
    with zipfile.ZipFile(os.path.join(BASE_DIR, filename), "r") as archive:
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
        "title": info.get("CFBundleDisplayName") or info.get("CFBundleName") or filename[:-4]
    }

@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")

@app.get("/ipa")
def ipa_redirect():
    return redirect("/ipa/", code=302)

@app.get("/ipa/")
def ipa_library():
    cards = []
    for filename in get_ipa_files():
        safe_name = html.escape(filename)
        manifest_url = SITE_URL + url_for("manifest", filename=filename)
        install_url = "itms-services://?action=download-manifest&url=" + quote(manifest_url, safe="")
        download_url = url_for("download_ipa", filename=filename)
        cards.append(
            '<article class="app-card"><div class="app-main">'
            '<div class="app-icon">IPA</div><div class="app-info"><h2>' + safe_name +
            '</h2><p>iOS Application <span>·</span> IPA</p></div><span class="version">IPA</span></div>'
            '<a class="install" href="' + html.escape(install_url, quote=True) +
            '"><span>INSTALL</span><span class="arrow">↗</span></a>'
            '<a class="download" href="' + html.escape(download_url, quote=True) +
            '">Download IPA</a></article>'
        )
    if not cards:
        cards.append('<p class="sub">No IPA files are available yet.</p>')
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#101116">
<title>IPA Library — neveripa</title><link rel="stylesheet" href="/style.css">
<style>.library{width:min(100% - 40px,680px);margin:0 auto;padding:36px 0 64px}
.library-head{margin:30px 0}.library-head h1{font-size:clamp(36px,9vw,56px);margin:8px 0}
.app-card{margin:18px 0}.download{display:block;text-align:center;margin-top:14px;color:#aeb2c2;text-decoration:none;font-size:13px}
.back{color:#aeb2c2;text-decoration:none;font-size:13px}</style></head><body><main class="library">
<a class="back" href="/">← HOME</a><header class="library-head"><p class="eyebrow">IOS APPLICATION DISTRIBUTION</p>
<h1>IPA <span>LIBRARY</span></h1><p class="sub">Choose an application to install.</p></header>""" + "".join(cards) + """
<footer>NEVERIPA <span>·</span> APP DISTRIBUTION</footer></main></body></html>"""
    return Response(page, mimetype="text/html")

@app.get("/manifest/<path:filename>.plist")
def manifest(filename):
    filename = os.path.basename(filename)
    if filename not in get_ipa_files():
        abort(404)
    try:
        info = read_ipa_info(filename)
    except (zipfile.BadZipFile, KeyError, ValueError, plistlib.InvalidFileException):
        abort(422)
    data = {"items": [{"assets": [{"kind": "software-package",
            "url": SITE_URL + url_for("download_ipa", filename=filename)}],
            "metadata": {"bundle-identifier": info["bundle_id"],
            "bundle-version": info["version"], "kind": "software", "title": info["title"]}}]}
    return Response(plistlib.dumps(data, fmt=plistlib.FMT_XML), mimetype="application/xml")

@app.get("/download/<path:filename>")
def download_ipa(filename):
    filename = os.path.basename(filename)
    if filename not in get_ipa_files():
        abort(404)
    return send_from_directory(BASE_DIR, filename, as_attachment=False)

@app.get("/<path:filename>")
def files(filename):
    return send_from_directory(BASE_DIR, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
