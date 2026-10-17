# Indeed discovery workflow

This is a **job discovery and review queue**, not a working authenticated auto-apply bot. Indeed can block automated access, and GitHub-hosted runners may be challenged. No credentials, cookies or passwords are stored.

Every day at **08:00 IST**, GitHub Actions attempts to find recent India-wide Electrical Engineering fresher/trainee and Logistics Analyst/EXIM listings. It removes duplicates, and creates an artifact containing `review_queue.csv` with job links and `report.json` with errors and counts. Application status is always ACTION_REQUIRED, never Applied.

To run on a phone: open the repository in mobile browser > Actions > Indeed Job Discovery > Run workflow (on the main branch). Open the completed run > Artifacts > indeed-review-queue to download results.

Optional Telegram summaries: repository Settings > Secrets and variables > Actions > New repository secret; create `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Never paste tokens in issues or public code.

Limitations: Search markup can change; no guarantee of job results. This workflow does not log in, generate tailored resumes or submit applications. Prefer Indeed's own job alerts as fallback if pages block runners. Be aware scheduled GitHub Actions may run late or be disabled due to repository inactivity.
