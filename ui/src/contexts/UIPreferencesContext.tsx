/**
 * UI Preferences Context - Quantum UI Settings
 * =============================================
 * 
 * Manages theme, density, and motion preferences.
 * Persists to localStorage and respects system preferences.
 */

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';

// Types
type Theme = 'light' | 'dark' | 'system';
type Density = 'compact' | 'comfortable' | 'spacious';
type Motion = 'full' | 'reduce';

interface UIPreferences {
  theme: Theme;
  density: Density;
  motion: Motion;
}

interface UIPreferencesContextValue extends UIPreferences {
  setTheme: (theme: Theme) => void;
  setDensity: (density: Density) => void;
  setMotion: (motion: Motion) => void;
  resolvedTheme: 'light' | 'dark';
}

const STORAGE_KEY = 'erpx_ui_prefs';

const defaultPreferences: UIPreferences = {
  theme: 'system',
  density: 'comfortable',
  motion: 'full',
};

function loadPreferences(): UIPreferences {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return { ...defaultPreferences, ...JSON.parse(stored) };
    }
  } catch (e) {
    console.warn('Failed to load UI preferences:', e);
  }
  return defaultPreferences;
}

function savePreferences(prefs: UIPreferences) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch (e) {
    console.warn('Failed to save UI preferences:', e);
  }
}

function getResolvedTheme(theme: Theme): 'light' | 'dark' {
  if (theme === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return theme;
}

const UIPreferencesContext = createContext<UIPreferencesContextValue | null>(null);

export function UIPreferencesProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<UIPreferences>(loadPreferences);
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>(() => 
    getResolvedTheme(loadPreferences().theme)
  );
  
  // Update resolved theme when system preference changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    const handleChange = () => {
      if (prefs.theme === 'system') {
        setResolvedTheme(mediaQuery.matches ? 'dark' : 'light');
      }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [prefs.theme]);
  
  // Update resolved theme when theme preference changes
  useEffect(() => {
    setResolvedTheme(getResolvedTheme(prefs.theme));
  }, [prefs.theme]);
  
  // Apply preferences to document
  useEffect(() => {
    const root = document.documentElement;
    
    // Theme
    root.setAttribute('data-theme', resolvedTheme);
    
    // Density
    root.setAttribute('data-density', prefs.density);
    
    // Motion (also check system preference)
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const effectiveMotion = prefersReducedMotion || prefs.motion === 'reduce' ? 'reduce' : 'full';
    root.setAttribute('data-motion', effectiveMotion);
    
    // Save to localStorage
    savePreferences(prefs);
  }, [prefs, resolvedTheme]);
  
  const setTheme = useCallback((theme: Theme) => {
    setPrefs(prev => ({ ...prev, theme }));
  }, []);
  
  const setDensity = useCallback((density: Density) => {
    setPrefs(prev => ({ ...prev, density }));
  }, []);
  
  const setMotion = useCallback((motion: Motion) => {
    setPrefs(prev => ({ ...prev, motion }));
  }, []);
  
  const value: UIPreferencesContextValue = {
    ...prefs,
    setTheme,
    setDensity,
    setMotion,
    resolvedTheme,
  };
  
  return (
    <UIPreferencesContext.Provider value={value}>
      {children}
    </UIPreferencesContext.Provider>
  );
}

export function useUIPreferences() {
  const context = useContext(UIPreferencesContext);
  if (!context) {
    throw new Error('useUIPreferences must be used within UIPreferencesProvider');
  }
  return context;
}

// Hook for quick theme check
export function useTheme() {
  const { resolvedTheme } = useUIPreferences();
  return resolvedTheme;
}
