# Robo Architect Lite — Installers

A desktop app for designing software with AI: requirements and proposals become bounded contexts,
aggregates, events and processes in a graph, and the code is planned and implemented from that
design by **Claude Code** on your computer. It also analyzes legacy code and databases. This
repository holds **installers only**.

Product page: https://www.uengine.org/en/contents/roboarchitect.html ·
Tutorial (Korean, with a video for every chapter): https://www.uengine.org/docs/robo-architect/

## Download

Get the file from the [latest release](https://github.com/uengine-oss/robo-architect-lite-releases/releases/latest).

| OS | File |
|---|---|
| macOS (Apple Silicon) | [Robo-Architect-Lite-mac-arm64.dmg](https://github.com/uengine-oss/robo-architect-lite-releases/releases/latest/download/Robo-Architect-Lite-mac-arm64.dmg) — drag the app to Applications |
| Windows | coming later |

## Requirements

- **macOS on Apple Silicon** (M1 or later). 16 GB of memory or more is recommended.
- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**, running. The graph database
  (Ontological DB), the Bolt gateway, the data fabric and the analysis services run as seven containers
  that the app starts and stops itself (about 2 GB of memory while idle).
- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** installed and signed in (`claude`
  in a terminal works). Proposals, plans, implementation and the legacy analyzer's language model all
  go through it — no API key is needed.
- About 6 GB of free disk space.

## First launch

- **The app is not notarized by Apple yet, so you allow it once.** Drag it to Applications and open it.
  When macOS says it "could not verify 'Robo Architect Lite' is free of malware", click **Done**, open
  **System Settings › Privacy & Security**, click **Open Anyway** next to Robo Architect Lite, enter your
  password and click **Open**. On macOS 14 and earlier, right-click the app and choose **Open**.
- **The first launch downloads the seven Docker images — about 1.1 GB (about 4.8 GB on disk)** from
  the GitHub Container Registry (`ghcr.io/uengine-oss/robo-architect-lite-*`). The home screen shows
  which image is downloading and how far it is. Later launches start in under a minute.
- If the app says Docker is not available, start Docker Desktop and open the app again.
- Your data stays on this computer: the app's settings in
  `~/Library/Application Support/Robo Architect Lite`, the graphs in a Docker volume of the
  `robo-architect-desktop` Compose project.
- **Language**: the app follows your OS language (English or Korean).

## Contact

Robo Architect is developed by [uEngine Solutions](https://www.uengine.org).
Contact: https://www.uengine.org/contents/contactus.html
