import type { Metadata } from "next";
import { geist, geistMono, serif } from "./fonts";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Flowline — Inspection Decision Support",
  description:
    "Alberta pipeline inspection prioritization dashboard. Supports engineering judgment; does not replace it.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geist.variable} ${geistMono.variable} ${serif.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-bg font-sans text-ink">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
