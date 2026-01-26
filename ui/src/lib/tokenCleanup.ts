/**
 * One-time token cleanup after security update.
 * Removes old erpx_token from localStorage to force re-login.
 */
export function cleanupTokenOnce(): void {
  try {
    const flag = localStorage.getItem('erpx_token_cleanup_v1');
    if (flag) return;
    
    // Clear the old token
    localStorage.removeItem('erpx_token');
    
    // Mark cleanup as done
    localStorage.setItem('erpx_token_cleanup_v1', '1');
    
    console.log('[Security] Token cleanup completed - please login again');
  } catch (e) {
    // Ignore errors in case localStorage is not available
  }
}
