import type { Metadata } from "next";
import "./globals.css";
import AppHeader from "@/components/layout/AppHeader";

export const metadata: Metadata = {
  title: "IT - IPO Trace",
  description: "최근 1년 신규상장 기업 추적 웹앱"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <AppHeader />
        {children}
      </body>
    </html>
  );
}