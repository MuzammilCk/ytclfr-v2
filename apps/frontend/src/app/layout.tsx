import type { Metadata } from "next";
import Link from "next/link";
import { Space_Grotesk, Source_Sans_3 } from "next/font/google";

import "./globals.css";

const displayFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "700"],
});

const bodyFont = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "600"],
});

export const metadata: Metadata = {
  title: "YTCLFR",
  description: "Convert YouTube videos into structured knowledge.",
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body className={`${displayFont.variable} ${bodyFont.variable}`}>
        <div aria-hidden className="ambient-gradient" />
        <header className="site-header">
          <Link className="brand" href="/">
            YTCLFR
          </Link>
          <nav className="site-nav">
            <Link href="/">Home</Link>
            <Link href="/status">Processing Status</Link>
            <Link href="/result">Result</Link>
          </nav>
        </header>
        <main className="page-shell">{children}</main>
      </body>
    </html>
  );
}
