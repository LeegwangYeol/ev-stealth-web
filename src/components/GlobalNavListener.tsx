'use client';

import { useEffect } from 'react';

/**
 * GlobalNavListener encapsulates global event listeners for navigation interactions:
 * 1. Auto-closing the mobile navigation drawer when an internal link is clicked.
 * 2. Closing the drawer and returning focus to summary on Escape key press.
 *
 * All global event listeners registered via window.addEventListener are explicitly
 * cleaned up via window.removeEventListener on component unmount to prevent memory leaks.
 */
export default function GlobalNavListener() {
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const drawer = document.getElementById('mobile-nav-drawer');
      if (drawer && drawer.hasAttribute('open')) {
        const target = e.target as HTMLElement | null;
        if (target && target.closest && target.closest('#mobile-nav-drawer a')) {
          drawer.removeAttribute('open');
        }
      }
    };

    const handleKeydown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === 'Esc') {
        const drawer = document.getElementById('mobile-nav-drawer');
        if (drawer && drawer.hasAttribute('open')) {
          drawer.removeAttribute('open');
          const summary = drawer.querySelector('summary');
          if (summary) {
            summary.focus();
          }
        }
      }
    };

    window.addEventListener('click', handleClick);
    window.addEventListener('keydown', handleKeydown);

    return () => {
      window.removeEventListener('click', handleClick);
      window.removeEventListener('keydown', handleKeydown);
    };
  }, []);

  return null;
}
