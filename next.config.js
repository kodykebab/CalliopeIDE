const { withSentryConfig } = require('@sentry/nextjs');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Sentry configuration
  sentry: {
    // Suppress source map upload logs during build
    silent: true,
    org: process.env.SENTRY_ORG,
    project: process.env.SENTRY_PROJECT,
  },

  // Optional: Disable source map upload if Sentry is not configured
  ...(process.env.NEXT_PUBLIC_ENABLE_MONITORING !== 'true' && {
    sentry: {
      disableServerWebpackPlugin: true,
      disableClientWebpackPlugin: true,
    }
  })
}

const sentryWebpackPluginOptions = {
  // Additional config options for the Sentry Webpack plugin
  silent: true, // Suppresses all logs
  
  // For all available options, see:
  // https://github.com/getsentry/sentry-webpack-plugin#options.
}

// Only wrap with Sentry config if monitoring is enabled
module.exports = process.env.NEXT_PUBLIC_ENABLE_MONITORING === 'true' 
  ? withSentryConfig(nextConfig, sentryWebpackPluginOptions)
  : nextConfig
