import '@testing-library/jest-dom';

// Mock Canvas API for jsdom
HTMLCanvasElement.prototype.getContext = jest.fn() as any;
