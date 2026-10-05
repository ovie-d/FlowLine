import type { Metadata } from "next";
import { geist, geistMono, serif } from "./fonts";
import { IntroGate } from "@/components/brand/IntroGate";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Flowline — Hazard Forecast",
  description:
    "Forecasts the mix of likely pipeline hazards and the crews to prepare, from public incident history. Supports engineering judgment; does not certify any pipe as safe.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geist.variable} ${geistMono.variable} ${serif.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-bg font-sans text-fg">
        <Providers>
          <IntroGate>{children}</IntroGate>
        </Providers>
      </body>
    </html>
  );
}
