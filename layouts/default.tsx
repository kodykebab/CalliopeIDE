import { Link } from "@heroui/link";

import { Head } from "./head";

export default function DefaultLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex flex-col h-screen">
      <Head />
      <main 
        role="main" 
        aria-label="Main content"
        className="container mx-auto max-w-7xl px-6 flex-grow pt-16"
      >
        {children}
      </main>
      <footer 
        role="contentinfo"
        className="w-full flex items-center justify-center py-3"
      >
        <Link
          isExternal
          className="flex items-center gap-1 text-current focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-md px-2 py-1"
          href="https://www.heroui.com"
          title="heroui.com homepage"
          aria-label="Powered by HeroUI - Visit HeroUI homepage"
        >
          <span className="text-default-600">Powered by</span>
          <p className="text-primary">HeroUI</p>
        </Link>
      </footer>
    </div>
  );
}
