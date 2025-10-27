(function () {
  const root = document.querySelector('[data-options-sidebar]');
  if (!root) return;

  const openBtn = root.querySelector('[data-options-sidebar-open]');
  const closeButtons = Array.from(root.querySelectorAll('[data-options-sidebar-close]'));
  const container = root.querySelector('[data-options-sidebar-panel]');
  const backdrop = root.querySelector('[data-options-sidebar-backdrop]');
  const focusableSelectors = [
    'a[href]',
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[tabindex]:not([tabindex="-1"])'
  ];

  let lastFocused = null;

  const getFocusable = () =>
    Array.from(container.querySelectorAll(focusableSelectors.join(',')))
      .filter((el) => el.offsetParent !== null || getComputedStyle(el).position === 'fixed');

  const trapFocus = (event) => {
    const focusable = getFocusable();
    if (!focusable.length) {
      event.preventDefault();
      container.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const setOpenState = (open) => {
    root.classList.toggle('options-sidebar--open', open);
    container.setAttribute('aria-hidden', String(!open));
    container.setAttribute('tabindex', open ? '0' : '-1');
    openBtn.setAttribute('aria-expanded', String(open));
    document.body.style.overflow = open ? 'hidden' : '';

    if (open) {
      lastFocused = document.activeElement;
      window.setTimeout(() => {
        const focusable = getFocusable();
        (focusable[0] || container).focus();
      }, 30);
      document.addEventListener('keydown', onKeydown);
      container.addEventListener('keydown', onContainerKeydown);
    } else {
      document.removeEventListener('keydown', onKeydown);
      container.removeEventListener('keydown', onContainerKeydown);
      if (lastFocused) {
        (lastFocused).focus?.();
      }
    }
  };

  const onKeydown = (event) => {
    if (event.key === 'Escape') {
      setOpenState(false);
    }
  };

  const onContainerKeydown = (event) => {
    if (event.key === 'Tab') {
      trapFocus(event);
    }
  };

  openBtn?.addEventListener('click', () => setOpenState(true));
  closeButtons.forEach((btn) => btn.addEventListener('click', () => setOpenState(false)));
  backdrop?.addEventListener('click', () => setOpenState(false));

  // Close when focus leaves via some other mechanism (e.g. history back)
  window.addEventListener('popstate', () => setOpenState(false));
})();
