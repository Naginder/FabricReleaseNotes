# GitHub Pages Solution (No Azure)

This folder contains an alternative deployment path for the Fabric release tracker that runs on GitHub Pages.

## Architecture
- Static frontend: `GHFabricReleaseNotes/docs/index.html`
- Persistent data layer: `GHFabricReleaseNotes/docs/data/releases.json`
- Data refresh job: `GHFabricReleaseNotes/scripts/update_data.py`
- Automation: `GHFabricReleaseNotes/.github/workflows/update-fabric-release-data.yml`

The JSON file is committed to the repository, so it acts as a simple durable datastore that GitHub Pages can read directly.

## Local Test
1. From repo root, install refresh script dependencies:
   - `pip install -r GHFabricReleaseNotes/scripts/requirements.txt`
2. Refresh data:
   - `python GHFabricReleaseNotes/scripts/update_data.py`
3. Open `GHFabricReleaseNotes/docs/index.html` in a browser.

## Host on GitHub Pages
1. Push this repository to GitHub.
2. In GitHub, go to **Settings > Pages**.
3. Under **Build and deployment**, set:
   - **Source**: Deploy from a branch
   - **Branch**: `main` (or your default branch)
   - **Folder**: `/docs` (when `GHFabricReleaseNotes` is the repository root)
4. Save settings.
5. Wait for the Pages deployment and open the provided URL.

## Keep Data Fresh
- Scheduled refresh is configured in `GHFabricReleaseNotes/.github/workflows/update-fabric-release-data.yml` (every 6 hours).
- You can run it manually in GitHub via **Actions > Update Fabric Release Data > Run workflow**.
- Each run updates `GHFabricReleaseNotes/docs/data/releases.json` and commits changes when data changed.

## Notes
- GitHub Pages is static; the page itself cannot write data.
- Persistence is handled by committing the JSON file from GitHub Actions.
