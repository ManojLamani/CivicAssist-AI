import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CivicAssist AI | Development foundation",
  description: "Independent civic grievance intelligence for Bengaluru. Development setup.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en">
    <body>{children}</body>
  </html>;
}
