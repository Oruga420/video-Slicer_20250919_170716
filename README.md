# Video Slicer

Neon-soaked web app that slices any uploaded video into one PNG frame per second, bundles the frames into a zip, and lets you download the whole stash. Built to deploy on Vercel with a retro 90s interface.

## Features

- Drag-and-drop any video format the browser can decode
- Pure client-side frame extraction using the HTML5 video element and canvas
- Automatic zipping with `jszip` and single-click download
- Animated retro UI with cyan, magenta, Ferrari red, and sunset orange accents
- Background effects that kick in while processing for a time-lapse vibe

## Tech Stack

- [Next.js 14](https://nextjs.org/) with the App Router
- React 18
- Canvas-based frame capture
- [`jszip`](https://stuk.github.io/jszip/)

## Getting Started

```bash
npm install
npm run dev
```

Open `http://localhost:3000` and start slicing.

## Deploying to Vercel

1. Push this project to a Git repo (GitHub, GitLab, Bitbucket).
2. Create a new Vercel project and import the repo.
3. Use the default settings for a Next.js app. No environment variables or build hooks are required.
4. Trigger a deployment and enjoy the neon.

## Notes

- Video processing is entirely client-side. Large uploads will consume browser memory and can take time, so consider trimming before upload if you run into limits.
- The progress indicator mirrors the frame capture loop, but zipping happens afterward; the status panel will keep you informed.
- The UI uses a Google-hosted font (`Press Start 2P`). If you need offline assets, download the font and serve it from `public`.
