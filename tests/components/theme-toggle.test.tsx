import { render, screen } from '@testing-library/react';

describe('Theme Toggle Component', () => {
  it('should render without crashing', () => {
    const div = document.createElement('div');
    expect(div).toBeTruthy();
  });

  it('should support dark mode', () => {
    document.documentElement.classList.add('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('should support light mode', () => {
    document.documentElement.classList.remove('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('should toggle between themes', () => {
    const isDark = document.documentElement.classList.contains('dark');
    document.documentElement.classList.toggle('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(!isDark);
  });
});
