import type { Metadata } from "next";
import localFont from "next/font/local";
import { GlobalChatAlerts } from "@/components/GlobalChatAlerts";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "MatchMe",
  description: "Друзья по взглядам и ценностям, не по внешности",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body
        className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}
      >
        <GlobalChatAlerts />
        {children}
      </body>
    </html>
  );
}
