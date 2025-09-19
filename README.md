# Video Slicer

Neon-soaked web app that slices any uploaded video into one PNG frame per second, bundles the frames into a zip, and lets you download the whole stash. Built to deploy on Vercel with a retro 90s interface.

## Features

- Drag-and-drop any video format that browsers support
- Client-side frame extraction powered by `@ffmpeg/ffmpeg` WebAssembly
- Automatic zipping with `jszip` and single-click download
- Animated retro UI with cyan, magenta, Ferrari red, and sunset orange accents
- Background effects that kick in while processing for a time-lapse vibe

## Tech Stack

- [Next.js 14](https://nextjs.org/) with the App Router
- React 18
- [`@ffmpeg/ffmpeg`](https://github.com/ffmpegwasm/ffmpeg.wasm) and [`@ffmpeg/util`](https://github.com/ffmpegwasm/ffmpeg.wasm/tree/master/packages/util)
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
3. Use the default settings for a Next.js app. No environment variables are required.
4. Trigger a deployment. The postinstall script copies the ffmpeg core bundle into `public/ffmpeg`, so the worker loads from your Vercel domain without extra configuration.

> To switch core versions or host the files elsewhere, update `scripts/copy-ffmpeg-core.mjs` and the `CORE_BASE_URL` constant in `app/page.tsx`. 

## Notes

- Video processing is entirely client-side. Large uploads will consume browser memory and can take time, so consider trimming before upload if you run into limits.
- The progress indicator mirrors the ffmpeg compilation progress, but zipping happens afterward; the status panel will keep you informed.
- The UI uses a Google-hosted font (`Press Start 2P`). If you need offline assets, download the font and serve it from `public`.
- The install script copies @ffmpeg/core assets into `public/ffmpeg` so the worker loads from the same origin during local dev and on Vercel.
