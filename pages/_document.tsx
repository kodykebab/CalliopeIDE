import { Html, Head, Main, NextScript } from "next/document";
import clsx from "clsx";

import { fontSans } from "@/config/fonts";

const themeScript = `
  (function () {
    try {
      var storageKey = "calliope-theme";
      var storedTheme = window.localStorage.getItem(storageKey);
      var theme = storedTheme === "light" || storedTheme === "dark" ? storedTheme : "dark";
      var root = document.documentElement;
      root.classList.toggle("dark", theme === "dark");
      root.dataset.theme = theme;
      root.style.colorScheme = theme;
    } catch (error) {
      document.documentElement.classList.add("dark");
      document.documentElement.dataset.theme = "dark";
      document.documentElement.style.colorScheme = "dark";
    }
  })();
`;

export default function Document() {
  return (
    <Html lang="en" suppressHydrationWarning>
      <Head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </Head>
      <body
        className={clsx(
          "min-h-screen bg-background text-foreground font-sans antialiased",
          fontSans.variable,
        )}
      >
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
