'use client';

import { useEffect, memo } from 'react';

/**
 * GlobalNavListener encapsulates global event listeners for navigation interactions:
 * 1. Auto-closing the mobile navigation drawer when an internal link is clicked.
 * 2. Closing the drawer and returning focus to summary on Escape key press.
 * 3. Ensuring root navigation links and logo have clean focus-visible:ring-2 styles under WCAG 2.4.7.
 * 4. Keyboard focus trapping within the mobile navigation drawer when open (WCAG 2.1.2 & 2.4.3).
 * 5. Synchronizing aria-expanded attribute on the summary toggle.
 * 6. Closing the mobile drawer automatically when viewport resizes to desktop (>= 768px).
 * 7. Closing the mobile drawer when navigating via browser history (popstate).
 *
 * All global event listeners registered on document, window, and drawer element are explicitly
 * cleaned up via removeEventListener on component unmount to guarantee zero memory leaks.
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

    const initialDrawer = document.getElementById('mobile-nav-drawer') as HTMLDetailsElement | null;

    const getDrawer = (): HTMLDetailsElement | null => {
      if (initialDrawer && initialDrawer.isConnected) {
        return initialDrawer;
      }
      return document.getElementById('mobile-nav-drawer') as HTMLDetailsElement | null;
    };

    const syncAriaExpanded = () => {
      const drawer = getDrawer();
      const summary = drawer?.querySelector('summary');
      if (summary && drawer) {
        summary.setAttribute('aria-expanded', drawer.hasAttribute('open') ? 'true' : 'false');
      }
    };

    if (initialDrawer) {
      initialDrawer.addEventListener('toggle', syncAriaExpanded);
      syncAriaExpanded();
    }

    const handleClick = (e: MouseEvent) => {
      const drawer = getDrawer();
      if (drawer && drawer.hasAttribute('open')) {
        const rawTarget = e.target as Node | null;
        const targetElement = (rawTarget instanceof Element ? rawTarget : rawTarget?.parentElement) as HTMLElement | null;
        if (!targetElement) {
          drawer.removeAttribute('open');
          syncAriaExpanded();
          return;
        }
        const isInsideDrawer = Boolean(targetElement.closest('#mobile-nav-drawer'));
        const isDrawerLink = Boolean(targetElement.closest('#mobile-nav-drawer a'));
        if (!isInsideDrawer || isDrawerLink) {
          drawer.removeAttribute('open');
          syncAriaExpanded();
        }
      }
    };

    const handleKeydown = (e: KeyboardEvent) => {
      const drawer = getDrawer();
      if (!drawer || !drawer.hasAttribute('open')) return;

      const summary = drawer.querySelector('summary') as HTMLElement | null;

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
          if (
            document.activeElement === firstElement ||
            document.activeElement === drawer ||
            !drawer.contains(document.activeElement)
          ) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (
            document.activeElement === lastElement ||
            !drawer.contains(document.activeElement)
          ) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    const handleResize = () => {
      const drawer = getDrawer();
      if (window.innerWidth >= 768 && drawer && drawer.hasAttribute('open')) {
        drawer.removeAttribute('open');
        syncAriaExpanded();
      }
    };

    const handlePopState = () => {
      const drawer = getDrawer();
      if (drawer && drawer.hasAttribute('open')) {
        drawer.removeAttribute('open');
        syncAriaExpanded();
      }
    };

    document.addEventListener('click', handleClick);
    document.addEventListener('keydown', handleKeydown);
    window.addEventListener('resize', handleResize);
    window.addEventListener('popstate', handlePopState);

    return () => {
      if (initialDrawer) {
        initialDrawer.removeEventListener('toggle', syncAriaExpanded);
      }
      const currentDrawer = getDrawer();
      if (currentDrawer && currentDrawer !== initialDrawer) {
        currentDrawer.removeEventListener('toggle', syncAriaExpanded);
      }
      document.removeEventListener('click', handleClick);
      document.removeEventListener('keydown', handleKeydown);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);

  return null;
});

export default GlobalNavListener;
