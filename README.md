# Job Autopilot Android Client

Native Android client for the Naukri Job Autopilot backend.

## Included behavior
- Electrical + Logistics tracks.
- Auto Submit shown as ON by default.
- Missing mandatory information goes to **Your Action Required** while the backend continues to the next job.
- Naukri login happens in an isolated in-app WebView without access to the dashboard bridge. The app can capture the logged-in WebView cookie header and send it to the configured private backend.
- OTP/CAPTCHA are completed manually by the user. The app does not bypass them.
- Backend URL and optional API key are stored locally on the phone. HTTPS is required; Android backup is disabled.
- Personal salary/profile values must be configured privately in the backend.

## Build
The included GitHub Actions workflow builds `app-debug.apk` automatically on push or manual workflow run.

## Important
This APK is a mobile client. Continuous scanning/resume generation/application processing still requires the companion backend to be hosted on a server. Do not expose a backend containing login-session data without authentication/TLS.
