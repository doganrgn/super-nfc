(function () {
  const root = document.querySelector('[data-options-sidebar]');
  if (!root) return;

  const openBtn = root.querySelector('[data-options-sidebar-open]');
  const closeButtons = Array.from(root.querySelectorAll('[data-options-sidebar-close]'));
  const container = root.querySelector('[data-options-sidebar-panel]');
  const backdrop = root.querySelector('[data-options-sidebar-backdrop]');
  const contentHost = root.querySelector('[data-options-sidebar-content]');
  const loadingNode = root.querySelector('[data-options-sidebar-loading]');
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
        lastFocused.focus?.();
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

  const renderSections = (data) => {
    if (!contentHost) return;
    contentHost.innerHTML = '';
    if (!data || !Array.isArray(data.sections) || !data.sections.length) {
      contentHost.innerHTML = '<p class="text-muted">Gösterilecek seçenek bulunamadı.</p>';
      return;
    }

    data.sections.forEach((section) => {
      const wrapper = document.createElement('section');
      wrapper.className = 'options-sidebar__section';
      if (section.title) {
        const heading = document.createElement('h3');
        heading.textContent = section.title;
        wrapper.appendChild(heading);
      }
      if (section.items && section.items.length) {
        const list = document.createElement('ul');
        list.className = 'list-unstyled options-sidebar__list';
        section.items.forEach((item) => {
          const li = document.createElement('li');
          const anchor = document.createElement('a');
          anchor.className = 'options-sidebar__link';
          anchor.href = item.url || '#';
          anchor.innerHTML = `
            <i class="bi bi-${item.icon || 'dot'}"></i>
            <span>${item.name || 'Seçenek'}</span>
          `;
          li.appendChild(anchor);
          list.appendChild(li);
        });
        wrapper.appendChild(list);
      }
      contentHost.appendChild(wrapper);
    });
  };

  const showError = (message) => {
    if (!contentHost) return;
    contentHost.innerHTML = `<div class="alert alert-warning">${message}</div>`;
  };

  const loadOptions = async () => {
    if (loadingNode) loadingNode.style.display = 'block';
    try {
      const response = await fetch('/api/options');
      if (!response.ok) throw new Error('Seçenekler alınamadı');
      const data = await response.json();
      renderSections(data);
    } catch (err) {
      console.error('Options sidebar error', err);
      showError('Seçenekler yüklenemedi. Lütfen daha sonra tekrar deneyin.');
    } finally {
      if (loadingNode) loadingNode.style.display = 'none';
    }
  };

  openBtn?.addEventListener('click', () => setOpenState(true));
  closeButtons.forEach((btn) => btn.addEventListener('click', () => setOpenState(false)));
  backdrop?.addEventListener('click', () => setOpenState(false));
  window.addEventListener('popstate', () => setOpenState(false));

  loadOptions();
})();
