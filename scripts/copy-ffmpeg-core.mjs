import { cp, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

const projectRoot = process.cwd();
const sourceDir = join(projectRoot, "node_modules", "@ffmpeg", "core", "dist", "esm");
const targetDir = join(projectRoot, "public", "ffmpeg");
const filesToCopy = ["ffmpeg-core.js", "ffmpeg-core.wasm"];

async function main() {
  if (!existsSync(sourceDir)) {
    console.warn("[copy-ffmpeg-core] Source directory not found:", sourceDir);
    return;
  }

  await mkdir(targetDir, { recursive: true });

  await Promise.all(
    filesToCopy.map(async (filename) => {
      await cp(join(sourceDir, filename), join(targetDir, filename));
    })
  );

  console.log("[copy-ffmpeg-core] Copied ffmpeg core assets to", targetDir);
}

main().catch((error) => {
  console.error("[copy-ffmpeg-core] Failed to copy ffmpeg core assets", error);
  process.exitCode = 1;
});
