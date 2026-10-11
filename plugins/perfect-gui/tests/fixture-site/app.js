const broken = window.UIAG_DEFECTS === true;
const english = {
  'nav.home': 'Home', 'nav.catalog': 'Catalogue', 'nav.more': 'More', 'more.help': 'Help', 'more.about': 'About us',
  'theme.toggle': 'Dark mode', 'lang.label': 'Language', 'home.title': 'Book a stay', 'home.intro': 'Find a place to stay for your next holiday.',
  'home.offers': 'Our offers', 'offer.chalet': 'Mountain chalet', 'offer.chalet.text': 'Three nights, breakfast included.',
  'offer.sea': 'Seaside house', 'offer.sea.text': 'One week, direct beach access.', 'offer.city': 'City flat', 'offer.city.text': 'Two nights near the museums.',
  'filters.toggle': 'Filter offers', 'filters.text': 'Filters: price, dates, travellers.', 'contact.open': 'Contact us',
  'contact.title': 'Contact', 'contact.text': 'Write to us at the address shown on the booking.', 'contact.close': 'Close',
  'news.title': 'Newsletter', 'news.email': 'Email address', 'news.submit': 'Subscribe', 'danger.title': 'Account',
  'danger.delete': 'Delete my account', 'footer.text': 'Demo site, no real data.', 'catalog.title': 'Catalogue',
  'catalog.sort.price': 'Sort by price', 'catalog.sort.name': 'Sort by name', 'tab.details': 'Details', 'tab.reviews': 'Reviews',
  'tab.details.text': 'All stays include bed linen.', 'tab.reviews.text': 'Guests rate our stays 4.6 out of 5.', 'catalog.add': 'Add to selection',
  'catalog.compare': 'Compare', 'catalog.share': 'Share',
};
const untranslatedWhenBroken = new Set(['home.intro', 'offer.chalet', 'offer.chalet.text', 'offer.sea', 'offer.sea.text', 'offer.city', 'offer.city.text', 'filters.toggle', 'contact.open', 'news.title', 'news.email', 'news.submit', 'footer.text', 'tab.details.text', 'tab.reviews.text', 'catalog.add', 'catalog.compare', 'catalog.share', 'home.offers', 'theme.toggle']);
const french = {};
document.querySelectorAll('[data-i18n]').forEach((node) => { french[node.dataset.i18n] = node.textContent; });

const applyLanguage = (lang) => {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach((node) => {
    const key = node.dataset.i18n;
    const keepFrench = lang === 'en' && broken && untranslatedWhenBroken.has(key);
    node.textContent = lang === 'en' && !keepFrench ? (english[key] || french[key]) : french[key];
  });
};
const languageSelect = document.getElementById('language');
languageSelect.addEventListener('change', () => applyLanguage(languageSelect.value));

const themeButton = document.getElementById('theme-toggle');
themeButton.addEventListener('click', () => {
  const dark = document.documentElement.classList.toggle('dark');
  document.documentElement.classList.toggle('light', !dark);
  themeButton.setAttribute('aria-pressed', String(dark));
  const featured = document.getElementById('featured-card');
  if (broken && featured) featured.style.background = dark ? '#ffffff' : '';
});

const moreButton = document.getElementById('more-button');
const moreMenu = document.getElementById('more-menu');
moreButton.addEventListener('click', () => {
  const open = moreButton.getAttribute('aria-expanded') !== 'true';
  moreButton.setAttribute('aria-expanded', String(open));
  moreMenu.hidden = !open;
  if (broken) moreMenu.style.width = '520px';
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && moreButton.getAttribute('aria-expanded') === 'true') {
    moreButton.setAttribute('aria-expanded', 'false');
    moreMenu.hidden = true;
    moreButton.focus();
  }
});

const filterButton = document.getElementById('filter-button');
if (filterButton) {
  filterButton.addEventListener('click', () => {
    if (broken) return;
    const panel = document.getElementById('filters');
    panel.hidden = !panel.hidden;
    filterButton.setAttribute('aria-expanded', String(!panel.hidden));
  });
}

const dialog = document.getElementById('contact-dialog');
const contactButton = document.getElementById('contact-button');
if (dialog && contactButton) {
  contactButton.addEventListener('click', () => { dialog.showModal(); document.body.style.overflow = 'hidden'; });
  dialog.addEventListener('close', () => { if (!broken) document.body.style.overflow = ''; });
  document.getElementById('contact-close').addEventListener('click', () => dialog.close());
}

const newsletter = document.getElementById('newsletter');
if (newsletter) {
  newsletter.addEventListener('submit', async (event) => {
    event.preventDefault();
    const status = document.getElementById('newsletter-status');
    const email = document.getElementById('news-email');
    if (!email.value.includes('@')) {
      email.setAttribute('aria-invalid', 'true');
      status.textContent = 'Adresse e-mail invalide : saisissez par exemple nom@exemple.fr';
      email.setAttribute('aria-describedby', 'newsletter-status');
      return;
    }
    email.removeAttribute('aria-invalid');
    try {
      await fetch('/api/newsletter', { method: 'POST', body: email.value });
      status.textContent = 'Inscription enregistrée.';
    } catch (error) {
      status.textContent = 'Le service est indisponible, réessayez plus tard.';
    }
  });
}

document.querySelectorAll('[role=tab]').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('[role=tab]').forEach((other) => {
      const selected = other === tab;
      other.setAttribute('aria-selected', String(selected));
      document.getElementById(other.getAttribute('aria-controls')).hidden = !selected;
    });
  });
});

document.querySelectorAll('[data-select-offer]').forEach((button) => {
  button.addEventListener('click', () => {
    const pressed = button.getAttribute('aria-pressed') !== 'true';
    button.setAttribute('aria-pressed', String(pressed));
    document.getElementById('selection-status').textContent = pressed ? 'Offre ajoutée à la sélection.' : 'Offre retirée de la sélection.';
  });
});

const deleteButton = document.getElementById('delete-account');
if (deleteButton) {
  deleteButton.addEventListener('click', () => { document.body.dataset.accountDeleted = 'true'; document.body.innerHTML = '<p>Compte supprimé.</p>'; });
}

const sort = new URLSearchParams(location.search).get('tri');
if (sort && !['prix', 'nom'].includes(sort) && broken) {
  throw new Error(`Tri inconnu : ${sort}`);
}
