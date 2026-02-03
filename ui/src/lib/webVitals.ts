/**
 * Web Vitals Instrumentation
 * ==========================
 * 
 * Tracks Core Web Vitals (CLS, LCP, FID, INP, TTFB)
 * and custom interaction metrics for Quantum UI.
 */

import { onCLS, onFID, onLCP, onINP, onTTFB } from 'web-vitals';

type MetricName = 'CLS' | 'FID' | 'LCP' | 'INP' | 'TTFB' | 'interaction';

interface MetricData {
  name: MetricName;
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  delta: number;
  id: string;
  navigationType?: string;
  interaction?: string;
}

// Rating thresholds (based on Core Web Vitals)
const THRESHOLDS = {
  CLS: { good: 0.1, poor: 0.25 },
  LCP: { good: 2500, poor: 4000 },
  FID: { good: 100, poor: 300 },
  INP: { good: 200, poor: 500 },
  TTFB: { good: 800, poor: 1800 },
  interaction: { good: 50, poor: 200 },
};

function getRating(name: MetricName, value: number): 'good' | 'needs-improvement' | 'poor' {
  const threshold = THRESHOLDS[name];
  if (value <= threshold.good) return 'good';
  if (value <= threshold.poor) return 'needs-improvement';
  return 'poor';
}

// Metric handler
function handleMetric(metric: any) {
  const data: MetricData = {
    name: metric.name as MetricName,
    value: metric.value,
    rating: getRating(metric.name as MetricName, metric.value),
    delta: metric.delta,
    id: metric.id,
    navigationType: metric.navigationType,
  };
  
  // Log to console (development)
  if (import.meta.env.DEV) {
    const color = data.rating === 'good' ? 'green' : data.rating === 'poor' ? 'red' : 'orange';
    console.log(
      `%c[WebVitals] ${data.name}: ${data.value.toFixed(2)} (${data.rating})`,
      `color: ${color}; font-weight: bold;`
    );
  }
  
  // Send to analytics endpoint (if configured)
  sendToAnalytics(data);
}

// Send to backend (optional)
async function sendToAnalytics(data: MetricData) {
  const endpoint = import.meta.env.VITE_VITALS_ENDPOINT;
  if (!endpoint) return;
  
  try {
    await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...data,
        timestamp: Date.now(),
        url: window.location.href,
        userAgent: navigator.userAgent,
      }),
      keepalive: true,
    });
  } catch (e) {
    // Silently fail - don't block user
  }
}

// Initialize Core Web Vitals tracking
export function initWebVitals() {
  onCLS(handleMetric);
  onFID(handleMetric);
  onLCP(handleMetric);
  onINP(handleMetric);
  onTTFB(handleMetric);
  
  if (import.meta.env.DEV) {
    console.log('%c[WebVitals] Initialized', 'color: blue; font-weight: bold;');
  }
}

// Custom interaction timing
let interactionStart: number | null = null;

export function startInteraction(name: string) {
  interactionStart = performance.now();
  if (import.meta.env.DEV) {
    console.log(`%c[Interaction] Start: ${name}`, 'color: gray;');
  }
}

export function endInteraction(name: string) {
  if (interactionStart === null) return;
  
  const duration = performance.now() - interactionStart;
  interactionStart = null;
  
  const data: MetricData = {
    name: 'interaction',
    value: duration,
    rating: getRating('interaction', duration),
    delta: duration,
    id: `${name}-${Date.now()}`,
    interaction: name,
  };
  
  if (import.meta.env.DEV) {
    const color = data.rating === 'good' ? 'green' : data.rating === 'poor' ? 'red' : 'orange';
    console.log(
      `%c[Interaction] ${name}: ${duration.toFixed(2)}ms (${data.rating})`,
      `color: ${color};`
    );
  }
  
  sendToAnalytics(data);
}

// Hook for measuring component interactions
export function useInteractionTiming() {
  return {
    start: startInteraction,
    end: endInteraction,
  };
}

// Measure render time
export function measureRender(componentName: string) {
  const start = performance.now();
  
  return () => {
    const duration = performance.now() - start;
    if (import.meta.env.DEV && duration > 16) { // More than 1 frame
      console.warn(`[Render] ${componentName} took ${duration.toFixed(2)}ms`);
    }
  };
}
