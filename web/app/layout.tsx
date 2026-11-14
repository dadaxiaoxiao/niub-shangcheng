import type { Metadata } from "next";

import "./globals.css";


export const metadata: Metadata = {
  title: "牛脖商城 | 为日常挑一件好东西",
  description: "茶、器物、香氛与日常小物。",
};


export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

