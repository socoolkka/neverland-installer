# neveripa

Flask-based web service for the Neverland iOS app landing page.

## Render settings
- Runtime: Python 3
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --bind 0.0.0.0:$PORT app:app`

The service serves `index.html`, `style.css`, `manifest.plist`, and the IPA file from the repository root.
The IPA must be present in the repository and already be signed for a permitted distribution method.
