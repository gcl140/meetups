document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('nav-toggle');
  const panel = document.getElementById('nav-mobile-panel');
  const openIcon = document.getElementById('nav-toggle-open-icon');
  const closeIcon = document.getElementById('nav-toggle-close-icon');
  if (toggle && panel) {
    toggle.addEventListener('click', () => {
      const isOpen = !panel.classList.contains('hidden');
      panel.classList.toggle('hidden', isOpen);
      openIcon.classList.toggle('hidden', !isOpen);
      closeIcon.classList.toggle('hidden', isOpen);
    });
  }

  const menuTrigger = document.getElementById('user-menu-trigger');
  const menuPanel = document.getElementById('user-menu-panel');
  const menuChevron = document.getElementById('user-menu-chevron');
  if (!menuTrigger || !menuPanel) return;

  const closeMenu = () => {
    menuPanel.classList.add('hidden');
    menuTrigger.setAttribute('aria-expanded', 'false');
    menuChevron?.classList.remove('rotate-180');
  };
  const openMenu = () => {
    menuPanel.classList.remove('hidden');
    menuTrigger.setAttribute('aria-expanded', 'true');
    menuChevron?.classList.add('rotate-180');
  };

  menuTrigger.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = !menuPanel.classList.contains('hidden');
    isOpen ? closeMenu() : openMenu();
  });
  document.addEventListener('click', (e) => {
    if (!menuPanel.classList.contains('hidden') && !menuPanel.contains(e.target)) closeMenu();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMenu();
  });
});
