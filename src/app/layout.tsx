import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";
import AppHeader from "@/components/layout/AppHeader";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL || "https://it-ipo-trace.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "IPO Trace | IPO 당시 주요 주주 구조와 상장 후 주가 흐름",
    template: "%s | IPO Trace",
  },
  description:
    "IPO Trace는 공모형 신규상장 기업의 IPO 당시 주요 주주 구조와 상장 후 주가 흐름을 추적하는 데이터 기반 웹앱입니다.",
  keywords: [
    "IPO Trace",
    "IPO",
    "신규상장",
    "공모가",
    "주요 주주",
    "지분율",
    "상장 후 수익률",
    "KOSPI",
    "KOSDAQ",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "ko_KR",
    url: "/",
    siteName: "IPO Trace",
    title: "IPO Trace | IPO 당시 주요 주주 구조와 상장 후 주가 흐름",
    description:
      "공모가, 상장일, IPO 당시 주요 주주 구조, 상장 후 수익률과 가격 흐름을 구조화해 보여주는 데이터 기반 웹앱",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "IPO Trace Open Graph Image",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "IPO Trace | IPO 당시 주요 주주 구조와 상장 후 주가 흐름",
    description:
      "공모가, 상장일, IPO 당시 주요 주주 구조, 상장 후 수익률과 가격 흐름을 추적하는 웹앱",
    images: ["/twitter-image"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <AppHeader />
        {children}
        <Analytics />
      </body>
    </html>
  );
}