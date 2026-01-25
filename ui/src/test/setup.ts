import '@testing-library/jest-dom/vitest';

// Mock scrollIntoView for jsdom
Element.prototype.scrollIntoView = () => {};
