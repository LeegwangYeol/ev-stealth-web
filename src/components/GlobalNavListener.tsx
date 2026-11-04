'use client';

import { useEffect, memo } from 'react';

/**
 * GlobalNavListener encapsulates global event listeners for navigation interactions:
 * 1. Auto-closing the mobile navigation drawer when an internal link is clicked.
 * 2. Closing the drawer and returning focus to summary on Escape key press.
 * 3. Ensuring root navigation links and logo have clean focus-visible:ring-2 styles under WCAG 2.4.7.
 *
 * All global event listeners registered via window.addEventListener are explicitly
 * cleaned up via window.removeEventListener on component unmount to prevent memory leaks.
 */
export const GlobalNavListener = memo(function GlobalNavListener() {
  useEffect(() => {
    // Ensure root navigation links and logo have clean focus-visible:ring-2 styles
    const header = document.querySelector('header');
    if (header) {
      const logo = header.querySelector<HTMLAnchorElement>('a[href="/"]');
      if (logo && !logo.classList.contains('focus-visible:ring-2')) {
        logo.classList.add(
          'focus:outline-none',
          'focus-visible:ring-2',
          'focus-visible:ring-blue-400',
          'focus-visible:ring-offset-2',
          'focus-visible:ring-offset-slate-900',
          'rounded-lg'
        );
      }
      const navLinks = header.querySelectorAll<HTMLAnchorElement>('nav a');
      navLinks.forEach((link) => {
        if (!link.classList.contains('focus-visible:ring-2')) {
          link.classList.add(
            'focus:outline-none',
            'focus-visible:ring-2',
            'focus-visible:ring-blue-400',
            'focus-visible:ring-offset-2',
            'focus-visible:ring-offset-slate-900',
            'rounded'
          );
        }
      });
    }

    const handleClick = (e: MouseEvent) => {
      const drawer = document.getElementById('mobile-nav-drawer');
      if (drawer && drawer.hasAttribute('open')) {
        const rawTarget = e.target as Node | null;
        const targetElement = (rawTarget instanceof Element ? rawTarget : rawTarget?.parentElement) as HTMLElement | null;
        if (targetElement) {
          const isInsideDrawer = Boolean(targetElement.closest('#mobile-nav-drawer'));
          const isDrawerLink = Boolean(targetElement.closest('#mobile-nav-drawer a'));
          if (!isInsideDrawer || isDrawerLink) {
            drawer.removeAttribute('open');
          }
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
});

export default GlobalNavListener;
