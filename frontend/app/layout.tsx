import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Grounded RAG",
  description: "Ask questions and verify answers against your documents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
