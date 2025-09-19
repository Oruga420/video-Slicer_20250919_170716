"use client";

import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { FFmpeg } from "@ffmpeg/ffmpeg";
import { fetchFile, toBlobURL } from "@ffmpeg/util";
import JSZip from "jszip";

type Status = "idle" | "loading" | "processing" | "zipping" | "done" | "error";

type FrameAsset = {
  name: string;
  data: Uint8Array;
};

const CORE_BASE_URL = "https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm";
const MAX_FRAMES = 36000;

export default function HomePage() {
  const ffmpegRef = useRef<FFmpeg | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("Drop a video to begin the slicing ritual.");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [frameCount, setFrameCount] = useState(0);

  // lazily load ffmpeg core when the component mounts
  useEffect(() => {
    let isActive = true;

    const loadFFmpeg = async () => {
      setStatus("loading");
      setMessage("Booting the neon engine...");

      try {
        const ffmpeg = new FFmpeg();

        ffmpeg.on("progress", ({ progress }) => {
          if (!isActive) return;
          setProgress(Math.round(progress * 100));
        });

        await ffmpeg.load({
          coreURL: await toBlobURL(`${CORE_BASE_URL}/ffmpeg-core.js`, "text/javascript"),
          wasmURL: await toBlobURL(`${CORE_BASE_URL}/ffmpeg-core.wasm`, "application/wasm"),
          workerURL: await toBlobURL(`${CORE_BASE_URL}/ffmpeg-core.worker.js`, "text/javascript")
        });

        if (!isActive) {
          ffmpeg.terminate();
          return;
        }

        ffmpegRef.current = ffmpeg;
        setIsReady(true);
        setStatus("idle");
        setMessage("Upload your video and let the frames fly.");
      } catch (error) {
        console.error(error);
        setStatus("error");
        setMessage("Could not boot the retro engine. Refresh and try again.");
      }
    };

    loadFFmpeg();

    return () => {
      isActive = false;
      ffmpegRef.current?.terminate();
      ffmpegRef.current = null;
    };
  }, []);

  const resetDownloadUrl = useCallback(() => {
    setDownloadUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return null;
    });
  }, []);

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    resetDownloadUrl();
    setVideoFile(file);
    setFrameCount(0);
    setProgress(0);
    setStatus("idle");
    setMessage(`Ready to slice ${file.name}. Hit the big button!`);
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (file) {
      resetDownloadUrl();
      setVideoFile(file);
      setFrameCount(0);
      setProgress(0);
      setStatus("idle");
      setMessage(`Ready to slice ${file.name}. Hit the big button!`);
    }
  };

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
  };

  const sanitizeExtension = (name: string) => {
    const idx = name.lastIndexOf(".");
    return idx >= 0 ? name.slice(idx) : ".mp4";
  };

  const cleanupArtifacts = async (ffmpeg: FFmpeg, names: string[]) => {
    for (const name of names) {
      try {
        await ffmpeg.deleteFile(name);
      } catch (error) {
        console.warn("Failed to delete", name, error);
      }
    }
  };

  const processVideo = async () => {
    if (!isReady || !videoFile || !ffmpegRef.current) {
      setMessage("Load a video first. The retro gods await offerings.");
      return;
    }

    resetDownloadUrl();
    setStatus("processing");
    setProgress(0);
    setMessage("Extracting one frame per second. Sit back and enjoy the glow.");

    const ffmpeg = ffmpegRef.current;
    const inputName = `input${sanitizeExtension(videoFile.name)}`;

    const generatedFrames: FrameAsset[] = [];
    const touchedFiles: string[] = [inputName];

    try {
      await ffmpeg.writeFile(inputName, await fetchFile(videoFile));

      const outputTemplate = `frame_%05d.png`;
      await ffmpeg.exec([
        "-i",
        inputName,
        "-vf",
        "fps=1,scale=-1:480:flags=lanczos",
        outputTemplate
      ]);

      // gather generated frames sequentially until one is missing
      for (let index = 1; index <= MAX_FRAMES; index += 1) {
        const name = `frame_${String(index).padStart(5, "0")}.png`;

        try {
          const fileData = await ffmpeg.readFile(name);
          const bytes = typeof fileData === "string" ? new TextEncoder().encode(fileData) : fileData;
          generatedFrames.push({ name, data: bytes });
          touchedFiles.push(name);
        } catch (error) {
          break;
        }
      }

      if (!generatedFrames.length) {
        throw new Error("No frames were generated. Try a different video.");
      }

      setStatus("zipping");
      setMessage("Packing your frames into a zip of pure nostalgia...");
      const zip = new JSZip();

      generatedFrames.forEach(({ name, data }) => {
        zip.file(name, data);
      });

      const blob = await zip.generateAsync({ type: "blob" });
      const url = URL.createObjectURL(blob);
      setDownloadUrl(url);
      setFrameCount(generatedFrames.length);
      setStatus("done");
      setMessage("Mission accomplished. Download your frame stash!");
    } catch (error) {
      console.error(error);
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Something glitched in the matrix.");
    } finally {
      await cleanupArtifacts(ffmpeg, touchedFiles);
    }
  };

  useEffect(() => {
    return () => {
      resetDownloadUrl();
    };
  }, []);

  const dropZoneClass = videoFile ? "drop-zone drop-zone--armed" : "drop-zone";
  const fxClass = status === "processing" || status === "zipping"
    ? "bg-effects bg-effects--active"
    : videoFile
      ? "bg-effects bg-effects--ready"
      : "bg-effects";
  const dropHint = videoFile ? videoFile.name : "Drop your video or click to upload";

  return (
    <main className="app-shell">
      <div className="crt-frame">
        <header className="header">
          <div className="title-glitch" aria-hidden="true">
            <span>Video</span>
            <span>Slicer</span>
          </div>
          <h1 className="sr-only">Video Slicer</h1>
          <p className="tagline">Slice time, frame by frame.</p>
        </header>

        <label
          className={dropZoneClass}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          <input
            type="file"
            accept="video/*"
            onChange={onFileChange}
            className="file-input"
          />
          <div className="drop-zone__art">
            <span className="drop-zone__icon">?</span>
            <span className="drop-zone__hint">{dropHint}</span>
            {videoFile && (
              <span className="drop-zone__meta">{(videoFile.size / (1024 * 1024)).toFixed(2)} MB</span>
            )}
          </div>
        </label>

        <button
          className="retro-button"
          disabled={!isReady || !videoFile || status === "processing" || status === "zipping" || status === "loading"}
          onClick={processVideo}
        >
          {status === "processing"
            ? "Slicing..."
            : status === "zipping"
              ? "Packing..."
              : !isReady
                ? "Booting..."
                : "Slice It!"}
        </button>

        <div className={`status-panel status-${status}`}>
          <p>{message}</p>
          {status === "processing" && (
            <div className="progress">
              <div className="progress__bar" style={{ width: `${progress}%` }} />
              <span>{progress}%</span>
            </div>
          )}
          {status === "done" && downloadUrl && (
            <div className="download-panel">
              <p>{frameCount} PNG frames ready.</p>
              <a className="retro-button secondary" href={downloadUrl} download={`frames-${videoFile?.name || "video"}.zip`}>
                Download Zip
              </a>
            </div>
          )}
        </div>

        <aside className="fx-panel">
          <div className={fxClass} aria-hidden="true">
            <div className="scanline" />
            <div className="matrix-rain" />
            <div className="pipe-grid" />
          </div>
        </aside>
      </div>
    </main>
  );
}




