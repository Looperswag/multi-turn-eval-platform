import "../styles/globals.css";
import type { Metadata } from "next";
import { Fraunces, Manrope, JetBrains_Mono } from "next/font/google";
import { Sidebar } from "@/components/sidebar";

/* Hallmark · root layout · EvalKit Studio
 * macrostructure: shell · theme: EvalKit Studio (custom)
 * font loader emits CSS vars consumed by tokens.css → --font-*-loader.
 */

const fraunces = Fraunces({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-display-loader",
  display: "swap",
});

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-body-loader",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono-loader",
  display: "swap",
});

export const metadata: Metadata = {
  title: "EvalKit · 多轮记忆机评平台",
  description: "AI 导购 chatbot 六大维度机评看板",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const fontVars = `${fraunces.variable} ${manrope.variable} ${jetbrainsMono.variable}`;

  return (
    <html lang="zh-CN" className={fontVars}>
      <body>
        <div className="grid min-h-screen lg:grid-cols-[240px_minmax(0,1fr)]">
          <Sidebar />
          <main className="min-w-0 px-md py-lg sm:px-lg sm:py-xl lg:px-2xl lg:py-2xl">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
