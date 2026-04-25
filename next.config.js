/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // Monaco editor uses dynamic imports for its web workers.
    // Marking it as an external resource avoids bundling issues in Next.js.
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      path: false,
    }
    return config
  },
}

module.exports = nextConfig
