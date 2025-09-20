"use client";

import { ChangeEvent, DragEvent, useCallback, useEffect, useState } from "react";
import JSZip from "jszip";

type Status = "idle" | "processing" | "zipping" | "done" | "error";

type FrameAsset = {
  name: string;
  data: Uint8Array;
};

const FRAME_INTERVAL_SECONDS = 1;
const MAX_FRAMES = 3600;
const TARGET_FRAME_HEIGHT = 480;

const clampTime = (time: number, duration: number) => {
  if (!Number.isFinite(duration) || duration <= 0) {
    return 0;
  }
  const epsilon = Math.min(0.08, duration / 200);
  const upperBound = Math.max(duration - epsilon, 0);
  return Math.min(time, upperBound);
};

const seekTo = (video: HTMLVideoElement, time: number) => {
  return new Promise<void>((resolve, reject) => {
    const handleSeeked = () => {
      cleanup();
      resolve();
    };

    const handleError = () => {
      cleanup();
      reject(new Error("Unable to seek within the video. Try a different file."));
    };

    const cleanup = () => {
      video.removeEventListener("seeked", handleSeeked);
      video.removeEventListener("error", handleError);
    };

    video.addEventListener("seeked", handleSeeked, { once: true });
    video.addEventListener("error", handleError, { once: true });
    video.currentTime = clampTime(time, video.duration || time);
  });
};

const blobToUint8Array = async (blob: Blob) => {
  const buffer = await blob.arrayBuffer();
  return new Uint8Array(buffer);
};

export default function HomePage() {
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("Drop a video to begin the slicing ritual.");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [frameCount, setFrameCount] = useState(0);

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

  const processVideo = async () => {
    if (!videoFile) {
      setMessage("Load a video first. The retro gods await offerings.");
      return;
    }

    resetDownloadUrl();
    setStatus("processing");
    setProgress(0);
    setMessage("Extracting one frame per second. Sit back and enjoy the glow.");

    const videoUrl = URL.createObjectURL(videoFile);
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;
    video.crossOrigin = "anonymous";
    video.src = videoUrl;

    try {
      await new Promise<void>((resolve, reject) => {
        const onLoaded = () => {
          cleanup();
          resolve();
        };
        const onError = () => {
          cleanup();
          reject(new Error("Could not read the video metadata."));
        };
        const cleanup = () => {
          video.removeEventListener("loadedmetadata", onLoaded);
          video.removeEventListener("error", onError);
        };
        video.addEventListener("loadedmetadata", onLoaded);
        video.addEventListener("error", onError);
      });

      if (video.readyState < 2) {
        await new Promise<void>((resolve) => {
          const cleanup = () => {
            video.removeEventListener("loadeddata", handleLoadedData);
            video.removeEventListener("error", handleError);
          };
          const handleLoadedData = () => {
            cleanup();
            resolve();
          };
          const handleError = () => {
            cleanup();
            resolve();
          };
          video.addEventListener("loadeddata", handleLoadedData, { once: true });
          video.addEventListener("error", handleError, { once: true });
        });
      }

      if (!Number.isFinite(video.duration) || video.duration <= 0) {
        throw new Error("This video has no measurable duration.");
      }

      const duration = video.duration;
      const targetTimes: number[] = [];
      let currentTime = 0;

      while (currentTime < duration && targetTimes.length < MAX_FRAMES) {
        targetTimes.push(clampTime(currentTime, duration));
        currentTime += FRAME_INTERVAL_SECONDS;
      }

      if (targetTimes.length === 0) {
        targetTimes.push(0);
      } else if (targetTimes[targetTimes.length - 1] < clampTime(duration, duration) && targetTimes.length < MAX_FRAMES) {
        targetTimes.push(clampTime(duration, duration));
      }

      const canvas = document.createElement("canvas");
      const aspectRatio = video.videoWidth && video.videoHeight ? video.videoWidth / video.videoHeight : 16 / 9;
      const targetHeight = Math.min(TARGET_FRAME_HEIGHT, video.videoHeight || TARGET_FRAME_HEIGHT);
      const targetWidth = Math.round(targetHeight * aspectRatio);
      canvas.width = targetWidth;
      canvas.height = targetHeight;

      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) {
        throw new Error("Canvas drawing is not supported in this browser.");
      }

      const generatedFrames: FrameAsset[] = [];

      for (let index = 0; index < targetTimes.length; index += 1) {
        const time = targetTimes[index];
        await seekTo(video, time);
        context.drawImage(video, 0, 0, targetWidth, targetHeight);

        const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
        if (!blob) {
          continue;
        }

        const data = await blobToUint8Array(blob);
        generatedFrames.push({
          name: `frame_${String(generatedFrames.length + 1).padStart(5, "0")}.png`,
          data
        });

        setProgress(Math.min(99, Math.round(((index + 1) / targetTimes.length) * 100)));
        setMessage(`Capturing frame ${index + 1} of ${targetTimes.length}...`);

        if (generatedFrames.length >= MAX_FRAMES) {
          break;
        }
      }

      if (!generatedFrames.length) {
        throw new Error("No frames were generated. Try a different video.");
      }

      setStatus("zipping");
      setMessage("Packing your frames into a zip of pure nostalgia...");
      setProgress(100);

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
      URL.revokeObjectURL(videoUrl);
      video.pause();
      video.remove();
    }
  };

  useEffect(() => {
    return () => {
      resetDownloadUrl();
    };
  }, [resetDownloadUrl]);

  const dropZoneClass = videoFile ? "drop-zone drop-zone--armed" : "drop-zone";
  const fxClass = status === "processing" || status === "zipping"
    ? "bg-effects bg-effects--active"
    : videoFile
      ? "bg-effects bg-effects--ready"
      : "bg-effects";
  const dropHint = videoFile ? videoFile.name : "Drop your video or click to upload";
  const isBusy = status === "processing" || status === "zipping";
  const canSlice = !!videoFile && !isBusy;

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

        <div className="button-row">
          <button
            className="retro-button"
            disabled={!canSlice}
            onClick={processVideo}
          >
            {isBusy
              ? status === "processing"
                ? "Slicing..."
                : "Packing..."
              : "Slice It!"}
          </button>
        </div>

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
