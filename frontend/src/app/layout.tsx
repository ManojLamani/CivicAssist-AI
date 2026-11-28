import type { Metadata } from "next";
import Link from "next/link";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

export const metadata: Metadata = {
  title: "CivicAssist AI",
  description: "Independent civic technology for Bengaluru.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
    <body><header className="site-header">
      <Link className="brand" href="/">CivicAssist <span>AI</span></Link>
      <nav aria-label="Main navigation"><Link href="/login">Sign in</Link><Link href="/register">Create account</Link></nav>
    </header><main>{children}</main></body>
  </html>;
}
