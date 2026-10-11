const broken = window.UIAG_DEFECTS === true;
const french = {
  'nav.home': 'Accueil', 'nav.catalog': 'Catalogue', 'nav.more': 'Plus', 'more.help': 'Aide', 'more.about': 'À propos',
  'theme.toggle': 'Mode sombre', 'lang.label': 'Langue', 'home.title': 'Réserver un séjour', 'home.intro': 'Trouvez un hébergement pour vos prochaines vacances.',
  'home.offers': 'Nos offres', 'offer.chalet': 'Chalet en montagne', 'offer.chalet.text': 'Trois nuits, petit-déjeuner compris.',
  'offer.sea': 'Maison au bord de mer', 'offer.sea.text': 'Une semaine, accès direct à la plage.', 'offer.city': 'Appartement en ville', 'offer.city.text': 'Deux nuits, proche des musées.',
  'filters.toggle': 'Filtrer les offres', 'filters.text': 'Filtres : prix, dates, voyageurs.', 'contact.open': 'Nous contacter',
  'contact.title': 'Contact', 'contact.text': "Écrivez-nous à l'adresse indiquée sur la réservation.", 'contact.close': 'Fermer',
  'news.title': "Lettre d'information", 'news.email': 'Adresse e-mail', 'news.submit': "S'inscrire", 'danger.title': 'Compte',
  'danger.delete': 'Supprimer mon compte', 'footer.text': 'Site de démonstration, aucune donnée réelle.', 'catalog.title': 'Catalogue',
  'catalog.sort.price': 'Trier par prix', 'catalog.sort.name': 'Trier par nom', 'tab.details': 'Détails', 'tab.reviews': 'Avis',
  'tab.details.text': 'Tous les séjours incluent le linge de maison.', 'tab.reviews.text': 'Les voyageurs notent nos séjours 4,6 sur 5.', 'catalog.add': 'Ajouter à la sélection',
  'catalog.compare': 'Comparer', 'catalog.share': 'Partager',
};
const untranslatedWhenBroken = new Set(['home.intro', 'offer.chalet', 'offer.chalet.text', 'offer.sea', 'offer.sea.text', 'offer.city', 'offer.city.text', 'filters.toggle', 'contact.open', 'news.title', 'news.email', 'news.submit', 'footer.text', 'tab.details.text', 'tab.reviews.text', 'catalog.add', 'catalog.compare', 'catalog.share', 'home.offers', 'theme.toggle']);
const english = {};
document.querySelectorAll('[data-i18n]').forEach((node) => { english[node.dataset.i18n] = node.textContent; });

const applyLanguage = (lang) => {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach((node) => {
    const key = node.dataset.i18n;
    const keepEnglish = lang === 'fr' && broken && untranslatedWhenBroken.has(key);
    node.textContent = lang === 'fr' && !keepEnglish ? (french[key] || english[key]) : english[key];
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
      status.textContent = 'Invalid email address: enter for example name@example.com';
      email.setAttribute('aria-describedby', 'newsletter-status');
      return;
    }
    email.removeAttribute('aria-invalid');
    try {
      await fetch('/api/newsletter', { method: 'POST', body: email.value });
      status.textContent = 'Subscription saved.';
    } catch (error) {
      status.textContent = 'The service is unavailable, try again later.';
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
    document.getElementById('selection-status').textContent = pressed ? 'Offer added to the selection.' : 'Offer removed from the selection.';
  });
});

const deleteButton = document.getElementById('delete-account');
if (deleteButton) {
  deleteButton.addEventListener('click', () => { document.body.dataset.accountDeleted = 'true'; document.body.innerHTML = '<p>Account deleted.</p>'; });
}

const sort = new URLSearchParams(location.search).get('sort');
if (sort && !['price', 'name'].includes(sort) && broken) {
  throw new Error(`Unknown sort: ${sort}`);
}
