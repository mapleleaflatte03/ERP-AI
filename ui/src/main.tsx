import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

// Security: One-time token cleanup after deploy
import { cleanupTokenOnce } from './lib/tokenCleanup';
import api from './lib/api';

// Run cleanup before React renders
cleanupTokenOnce();
api.clearToken?.();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
