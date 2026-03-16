import type { AppProps } from "next/app";

import { HeroUIProvider } from "@heroui/system";
import { useRouter } from "next/router";
import { useEffect } from "react";

import { fontSans, fontMono } from "@/config/fonts";
import { ThemeProvider } from "@/components/theme-provider";
import { captureException, initializeMonitoring } from "@/lib/monitoring";
import "@/styles/globals.css";

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();

  useEffect(() => {
    initializeMonitoring();
  }, []);

  return (
    <HeroUIProvider navigate={router.push}>
      <ThemeProvider>
        <Component {...pageProps} />
      </ThemeProvider>
    </HeroUIProvider>
  );
}

export const fonts = {
  sans: fontSans.style.fontFamily,
  mono: fontMono.style.fontFamily,
};
