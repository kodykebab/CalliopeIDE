import { SentryConfig } from './config/sentry';

// This file configures the initialization of Sentry on the browser side.
// The config you add here will be used whenever a page is visited.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

SentryConfig.initSentry();