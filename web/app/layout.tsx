import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GoldPan™ Master OS",
  description: "Internal operating system for GoldPan™",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-stone-950 text-stone-100 antialiased">
        {children}
      </body>
    </html>
  );
}
