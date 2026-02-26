import type { AppProps } from "next/app";

import { HeroUIProvider } from "@heroui/system";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import { useRouter } from "next/router";

import { fontSans, fontMono } from "@/config/fonts";
import "@/styles/globals.css";
import { ErrorBoundary } from "@/components/error-boundary";
import { ToastContainer } from "@/components/ui/error-alert";

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();

  return (
    <ErrorBoundary>
      <HeroUIProvider navigate={router.push}>
        <NextThemesProvider>
          <Component {...pageProps} />
          <ToastContainer />
        </NextThemesProvider>
      </HeroUIProvider>
    </ErrorBoundary>
  );
}

export const fonts = {
  sans: fontSans.style.fontFamily,
  mono: fontMono.style.fontFamily,
};
