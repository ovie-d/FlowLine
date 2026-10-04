import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";

export const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-display",
});

export const geist = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});
