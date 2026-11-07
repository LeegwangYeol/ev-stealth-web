'use client';

import { useEffect, memo } from 'react';

/**
 * GlobalNavListener encapsulates global event listeners for navigation interactions:
 * 1. Auto-closing the mobile navigation drawer when an internal link is clicked.
 * 2. Closing the drawer and returning focus to summary on Escape key press.
 * 3. Ensuring root navigation links and logo have clean focus-visible:ring-2 styles under WCAG 2.4.7.
 * 4. Keyboard focus trapping within the mobile navigation drawer when open (WCAG 2.1.2).
 * 5. Synchronizing aria-expanded attribute on the summary toggle.
 * 6. Closing the mobile drawer automatically when viewport resizes to desktop (>= 768px).
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

    const drawer = document.getElementById('mobile-nav-drawer') as HTMLDetailsElement | null;
    const summary = drawer?.querySelector('summary') as HTMLElement | null;

    const syncAriaExpanded = () => {
      if (summary && drawer) {
        summary.setAttribute('aria-expanded', drawer.hasAttribute('open') ? 'true' : 'false');
      }
    };

    if (drawer) {
      drawer.addEventListener('toggle', syncAriaExpanded);
      syncAriaExpanded();
    }

    const handleClick = (e: MouseEvent) => {
      if (drawer && drawer.hasAttribute('open')) {
        const rawTarget = e.target as Node | null;
        const targetElement = (rawTarget instanceof Element ? rawTarget : rawTarget?.parentElement) as HTMLElement | null;
        if (targetElement) {
          const isInsideDrawer = Boolean(targetElement.closest('#mobile-nav-drawer'));
          const isDrawerLink = Boolean(targetElement.closest('#mobile-nav-drawer a'));
          if (!isInsideDrawer || isDrawerLink) {
            drawer.removeAttribute('open');
            syncAriaExpanded();
          }
        }
      }
    };

    const handleKeydown = (e: KeyboardEvent) => {
      if (!drawer || !drawer.hasAttribute('open')) return;

      if (e.key === 'Escape' || e.key === 'Esc') {
        e.preventDefault();
        drawer.removeAttribute('open');
        syncAriaExpanded();
        if (summary) {
          summary.focus();
        }
        return;
      }

      // Keyboard Focus Trap (Tab and Shift+Tab)
      if (e.key === 'Tab') {
        const focusableElements = Array.from(
          drawer.querySelectorAll<HTMLElement>(
            'summary, a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
          )
        ).filter((el) => el.offsetParent !== null || el === summary);

        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstElement || document.activeElement === drawer) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    const handleResize = () => {
      if (window.innerWidth >= 768 && drawer && drawer.hasAttribute('open')) {
        drawer.removeAttribute('open');
        syncAriaExpanded();
      }
    };

    window.addEventListener('click', handleClick);
    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('resize', handleResize);

    return () => {
      if (drawer) {
        drawer.removeEventListener('toggle', syncAriaExpanded);
      }
      window.removeEventListener('click', handleClick);
      window.removeEventListener('keydown', handleKeydown);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return null;
});

export default GlobalNavListener;
