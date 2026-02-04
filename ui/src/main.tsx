import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

// Security: One-time token cleanup after deploy
import { cleanupTokenOnce } from './lib/tokenCleanup';

// Run cleanup before React renders
cleanupTokenOnce();

type UiPrefs = {
  theme: 'light' | 'dark';
  density: 'compact' | 'comfortable' | 'spacious';
  motion: 'normal' | 'reduced';
};

const DEFAULT_PREFS: UiPrefs = {
  theme: 'light',
  density: 'comfortable',
  motion: 'normal',
};

const loadUiPrefs = (): UiPrefs => {
  try {
    const raw = localStorage.getItem('erpx_ui_prefs');
    if (!raw) {
      localStorage.setItem('erpx_ui_prefs', JSON.stringify(DEFAULT_PREFS));
      return DEFAULT_PREFS;
    }
    const parsed = JSON.parse(raw);
    return {
      theme: parsed.theme || DEFAULT_PREFS.theme,
      density: parsed.density || DEFAULT_PREFS.density,
      motion: parsed.motion || DEFAULT_PREFS.motion,
    };
  } catch {
    return DEFAULT_PREFS;
  }
};

const applyUiPrefs = (prefs: UiPrefs) => {
  const root = document.documentElement;
  root.setAttribute('data-theme', prefs.theme);
  root.setAttribute('data-density', prefs.density);
  root.setAttribute('data-motion', prefs.motion);
};

const initWebVitals = () => {
  if (typeof window === 'undefined' || !('PerformanceObserver' in window)) return;

  const log = (name: string, value: number, detail?: Record<string, unknown>) => {
    console.info('[vitals]', { name, value, ...detail });
  };

  try {
    const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
    if (nav) {
      log('TTFB', nav.responseStart, { domContentLoaded: nav.domContentLoadedEventEnd });
    }
  } catch {
    // ignore
  }

  try {
    new PerformanceObserver((list) => {
      const entry = list.getEntries().at(-1);
      if (entry) log('LCP', entry.startTime);
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  } catch {
    // ignore
  }

  try {
    let clsValue = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as any) {
        if (!entry.hadRecentInput) {
          clsValue += entry.value;
        }
      }
    }).observe({ type: 'layout-shift', buffered: true });
    window.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        log('CLS', clsValue);
      }
    });
  } catch {
    // ignore
  }

  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as any) {
        const fid = entry.processingStart - entry.startTime;
        log('FID', fid);
      }
    }).observe({ type: 'first-input', buffered: true });
  } catch {
    // ignore
  }

  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as any) {
        if (entry.duration) {
          log('INP', entry.duration, { name: entry.name });
        }
      }
    }).observe({ type: 'event', buffered: true } as PerformanceObserverInit);
  } catch {
    // ignore
  }
};

const uiPrefs = loadUiPrefs();
applyUiPrefs(uiPrefs);
initWebVitals();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
