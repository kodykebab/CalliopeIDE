import '@testing-library/jest-dom';
import { TextEncoder, TextDecoder } from 'util';

// jsdom does not ship TextEncoder/TextDecoder globally — polyfill them.
if (typeof globalThis.TextEncoder === 'undefined') {
  // eslint-disable-next-line
  (globalThis as any).TextEncoder = TextEncoder;
}
if (typeof globalThis.TextDecoder === 'undefined') {
  // eslint-disable-next-line
  (globalThis as any).TextDecoder = TextDecoder;
}

// Mock Canvas API for jsdom
HTMLCanvasElement.prototype.getContext = jest.fn() as jest.Mock;
