import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ShortForge Dashboard",
  description: "Multi-tenant video generation SaaS",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
