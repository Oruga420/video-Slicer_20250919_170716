import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Video Slicer",
  description: "Slice videos into PNG frames and download them as a retro-styled zip package." 
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="retro-body">{children}</body>
    </html>
  );
}
