import { SentryConfig } from './config/sentry';

// This file configures the initialization of Sentry on the server side.
// The config you add here will be used whenever the server handles a request.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

SentryConfig.initSentry();