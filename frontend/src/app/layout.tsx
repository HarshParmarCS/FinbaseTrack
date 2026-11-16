import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import { QueryProvider } from "@/components/providers/query-provider";
import { Toaster } from "@/components/providers/toaster";
import { AuthProvider } from "@/features/auth/auth-provider";
import { publicEnv } from "@/config/env";
import "./globals.css";

// Inter matches the Finbase reference; the font variables feed --font-sans in globals.css.
const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: publicEnv.NEXT_PUBLIC_APP_NAME,
    template: `%s | ${publicEnv.NEXT_PUBLIC_APP_NAME}`,
  },
  description: "Lightweight project and task management for small teams.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full">
        <QueryProvider>
          <AuthProvider>{children}</AuthProvider>
        </QueryProvider>
        <Toaster />
      </body>
    </html>
  );
}
