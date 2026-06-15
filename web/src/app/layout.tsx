import type { Metadata, Viewport } from "next";
import { ShieldCheck } from "lucide-react";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Identity verification",
  description: "Verify your identity to continue.",
  applicationName: "Verify",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Verify" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover", // extend under the notch / home indicator
  themeColor: "#4f46e5",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-dvh antialiased">
        {/* Skip link for keyboard / screen-reader users (WCAG 2.4.1). */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
        >
          Skip to content
        </a>
        <header className="safe-top sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-md">
          <div className="mx-auto flex h-12 w-full max-w-md items-center gap-2 px-4">
            <span className="flex size-7 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-sm">
              <ShieldCheck className="size-4" aria-hidden />
            </span>
            <span className="text-sm font-semibold tracking-tight">Verify</span>
            <span className="ml-auto text-xs text-muted-foreground">Secure &amp; private</span>
          </div>
        </header>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
