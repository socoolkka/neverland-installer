# Neverland Installer

A small static iOS OTA installer landing page.

## Files
- `index.html`: landing page
- `style.css`: responsive dark styling
- `manifest.plist`: OTA manifest template

## Before publishing
1. Make the IPA available at the HTTPS URL in `manifest.plist`.
2. Replace `REPLACE_WITH_YOUR_APP_BUNDLE_ID` with the exact bundle identifier embedded in the signed IPA.
3. Set the manifest bundle version to the app's actual version.
4. Use an IPA signed for a distribution method that permits the intended devices and recipients.
5. Test the installation from Safari on a supported iPhone.

The repository must be publicly accessible for the raw GitHub URLs used in this starter template. Private GitHub repository raw URLs are not publicly downloadable by iOS OTA installation clients.