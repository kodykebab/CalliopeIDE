import type { AppProps } from "next/app";

import { HeroUIProvider } from "@heroui/system";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import { useRouter } from "next/router";

import { fontSans, fontMono } from "@/config/fonts";
import "@/styles/globals.css";
import ErrorBoundary, { AsyncErrorBoundary } from "@/components/ErrorBoundary";
import { ToastContainer } from "@/components/ErrorAlert";
import { SentryConfig, captureExceptionWithContext } from "@/config/sentry";

// Initialize Sentry
SentryConfig.initSentry();

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();

  const handleGlobalError = (error: Error, errorInfo?: any) => {
    console.error('Global error caught:', error, errorInfo);
    
    // Capture with Sentry if enabled
    captureExceptionWithContext(error, {
      errorInfo,
      component: 'App',
      route: router.pathname
    });
  };

  return (
    <ErrorBoundary onError={handleGlobalError}>
      <AsyncErrorBoundary onError={handleGlobalError}>
        <HeroUIProvider navigate={router.push}>
          <NextThemesProvider>
            <Component {...pageProps} />
            {/* Toast containers for all positions */}
            <ToastContainer position="top-right" />
            <ToastContainer position="top-left" />
            <ToastContainer position="bottom-right" />
            <ToastContainer position="bottom-left" />
            <ToastContainer position="top-center" />
          </NextThemesProvider>
        </HeroUIProvider>
      </AsyncErrorBoundary>
    </ErrorBoundary>
  );
}

export const fonts = {
  sans: fontSans.style.fontFamily,
  mono: fontMono.style.fontFamily,
};
