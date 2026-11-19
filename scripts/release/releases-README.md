# Robo Architect Lite — Installers

A desktop app for designing software with AI: requirements and proposals become bounded contexts,
aggregates, events and processes in a graph, and the code is planned and implemented from that
design by **Claude Code** on your computer. It also analyzes legacy code and databases. This
repository holds **installers only**.

Product page: https://www.uengine.org/en/contents/roboarchitect.html ·
Tutorial with a video for every chapter: https://www.uengine.org/en/docs/robo-architect/ (English) ·
https://www.uengine.org/docs/robo-architect/ (Korean)

## Download

Get the file from the [latest release](https://github.com/uengine-oss/robo-architect-lite-releases/releases/latest).

| OS | File |
|---|---|
| macOS (Apple Silicon) | [Robo-Architect-Lite-mac-arm64.dmg](https://github.com/uengine-oss/robo-architect-lite-releases/releases/latest/download/Robo-Architect-Lite-mac-arm64.dmg) — drag the app to Applications |
| Windows 10/11 (x64) | [Robo-Architect-Lite-Setup-win-x64.exe](https://github.com/uengine-oss/robo-architect-lite-releases/releases/latest/download/Robo-Architect-Lite-Setup-win-x64.exe) — run the installer (per user, no administrator rights) |

## Requirements

- **macOS on Apple Silicon** (M1 or later) or **Windows 10/11 (x64)**. 16 GB of memory or more is recommended.
- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**, running. The graph database
  (Ontological DB), the Bolt gateway, the data fabric, the analysis services, the wireframe
  renderer and the document-to-BPMN generator run as nine containers
  that the app starts and stops itself (about 2 GB of memory while idle). On Windows, use the default
  WSL 2 backend (Linux containers).
- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** installed and signed in (`claude`
  in a terminal works). The app's language model runs on it — proposals, plans, implementation, the
  legacy analyzer, document ingestion and wireframes — so no API key is needed. The home screen shows
  which Claude account the app runs on. On Windows, Claude Code needs
  [Git for Windows](https://git-scm.com/downloads/win).
- About 8 GB of free disk space.
- Optional: an **OpenAI API key**. Without it everything above works; with it, the data catalog also
  writes table descriptions and infers foreign keys, requirement mapping uses embeddings, and
  PDF documents can be turned into BPMN processes (OpenAI gpt-4o). The home
  screen's **AI key** row says how to set it (macOS: `launchctl setenv OPENAI_API_KEY <key>`; Windows:
  `setx OPENAI_API_KEY <key>`), then reopen the app.
- Optional: the **Figma desktop app**, for the Figma plugin (below).

## First launch

- **The app is not notarized by Apple yet, so you allow it once.** Drag it to Applications and open it.
  When macOS says it "could not verify 'Robo Architect Lite' is free of malware", click **Done**, open
  **System Settings › Privacy & Security**, click **Open Anyway** next to Robo Architect Lite, enter your
  password and click **Open**. On macOS 14 and earlier, right-click the app and choose **Open**.
- **Windows: the installer is not code-signed yet.** When "Windows protected your PC" appears, click
  **More info**, then **Run anyway**. Leave the install scope at the current user (no administrator
  rights), and clear the **Run** check box on the last screen — open the app from the Start menu, so it
  starts with your current environment.
- **The first launch downloads the Docker images — about 2 GB (about 6 GB on disk)** from
  the GitHub Container Registry (`ghcr.io/uengine-oss/robo-architect-lite-*` and the x64-only
  `process-gpt-bpmn-extractor`, which runs under Docker's emulation on Apple Silicon). The home screen shows
  which image is downloading and how far it is. Later launches start in under a minute.
- If the app says Docker is not available, start Docker Desktop and open the app again.
- Your data stays on this computer: the app's settings in
  `~/Library/Application Support/Robo Architect Lite` (Windows: `%APPDATA%\Robo Architect Lite`), the graphs in a Docker volume of the
  `robo-architect-desktop` Compose project.
- **Language**: the app follows your OS language (English or Korean).
- **Logs**: `logs/desktop-YYYY-MM-DD.log` in the settings folder above (the app's **Log folder** link opens it).

## Figma plugin

The plugin comes with the app. In the **Figma document link** dialog, click **Open plugin folder**: the app
puts `manifest.json` and `dist/plugin.js` in its settings folder (`…/Robo Architect Lite/figma-plugin`) and
opens it. In the Figma desktop app, choose **Plugins › Development › Import plugin from manifest…** and pick
that `manifest.json`, then run **RoboArchitect Sync** and connect it to the backend address the dialog shows.
The folder survives app updates and is refreshed each time you open it, so the plugin follows the app.

## Contact

Robo Architect is developed by [uEngine Solutions](https://www.uengine.org).
Contact: https://www.uengine.org/contents/contactus.html
