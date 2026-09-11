import type { Metadata } from "next";
import { Noto_Sans_Ethiopic } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const notoSansEthiopic = Noto_Sans_Ethiopic({
  subsets: ["ethiopic"],
  weight: ["400", "500", "600", "700", "800", "900"],
  variable: "--font-ethiopic",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ETHIOPIAN TIMES — News Intelligence & Publishing",
  description:
    "Ethiopian Times — Automated news intelligence, editorial verification, and visual publishing platform.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${notoSansEthiopic.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
