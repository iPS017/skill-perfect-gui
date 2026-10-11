(opts) => {
  const DESTRUCTIVE = new RegExp(opts.destructivePattern, 'i');
  const SETTING = new RegExp(opts.settingPattern, 'i');
  const origin = location.origin;

  const unique = (selector) => {
    try { return document.querySelectorAll(selector).length === 1; } catch (e) { return false; }
  };
  const quote = (value) => value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const stableId = (id) => !!id && !/([0-9a-f]{6,}|\d{4,}|^:r|^(radix|headlessui|react-aria|mui|ember|ext-gen|yui)[-_:]|[-_][a-z0-9]{8,}$)/i.test(id);
  const selectorFor = (el) => {
    if (stableId(el.id) && unique('#' + CSS.escape(el.id))) return '#' + CSS.escape(el.id);
    for (const attr of ['data-testid', 'data-test', 'data-cy', 'name', 'aria-label']) {
      const value = el.getAttribute(attr);
      if (!value || (attr === 'name' && !stableId(value))) continue;
      const candidate = `${el.tagName.toLowerCase()}[${attr}="${quote(value)}"]`;
      if (unique(candidate)) return candidate;
    }
    if (el.tagName === 'A' && el.getAttribute('href')) {
      const candidate = `a[href="${quote(el.getAttribute('href'))}"]`;
      if (unique(candidate)) return candidate;
    }
    if (el.tagName === 'INPUT' && el.name && el.value && ['radio', 'checkbox'].includes(el.type)) {
      const candidate = `input[name="${quote(el.name)}"][value="${quote(el.value)}"]`;
      if (unique(candidate)) return candidate;
    }
    const parts = [];
    for (let node = el; node && node.nodeType === 1 && node !== document.documentElement; node = node.parentElement) {
      if (stableId(node.id) && unique('#' + CSS.escape(node.id))) {
        parts.unshift('#' + CSS.escape(node.id));
        break;
      }
      let part = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const same = [...parent.children].filter((c) => c.tagName === node.tagName);
        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      if (unique(parts.join(' > '))) break;
    }
    return parts.join(' > ');
  };

  const textOf = (n) => ((n && (n.innerText || n.textContent)) || '').replace(/\s+/g, ' ').trim();
  const nameOf = (el) => {
    const labelledby = el.getAttribute('aria-labelledby');
    if (labelledby) {
      const t = labelledby.split(/\s+/).map((id) => document.getElementById(id)).filter(Boolean).map(textOf).join(' ').trim();
      if (t) return t;
    }
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
    if (el.labels && el.labels.length) return [...el.labels].map(textOf).join(' ').trim();
    if (['submit', 'button', 'reset'].includes(el.type) && el.tagName === 'INPUT') return el.value || '';
    const t = textOf(el);
    if (t) return t.slice(0, 80);
    const img = el.querySelector('img[alt], [aria-label]');
    if (img) return (img.getAttribute('alt') || img.getAttribute('aria-label') || '').trim();
    return (el.getAttribute('title') || el.getAttribute('placeholder') || '').trim();
  };
  const isVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) return false;
    if (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return false;
    return !el.closest('[inert], [aria-hidden=true]');
  };
  const contextOf = (el) => {
    const region = el.closest('nav, header, footer, aside, main, form, dialog, [role=dialog], [role=menu], [role=tablist], section');
    return region ? (region.getAttribute('aria-label') || region.tagName.toLowerCase()) : 'page';
  };

  const controls = [];
  const links = [];
  const params = {};
  const seen = new Set();
  const add = (el, kind, extra = {}) => {
    const selector = selectorFor(el);
    if (!selector || seen.has(selector)) return;
    seen.add(selector);
    const name = nameOf(el);
    const form = el.form || el.closest('form');
    const formAction = form ? (form.getAttribute('action') || '') : '';
    let risk = 'sur';
    if (DESTRUCTIVE.test(name) || DESTRUCTIVE.test(el.getAttribute('aria-label') || '') || DESTRUCTIVE.test(formAction)) risk = 'destructif';
    controls.push({
      selector, kind, name, risk,
      setting: SETTING.test(`${name} ${el.getAttribute('name') || ''} ${el.id || ''}`),
      region: contextOf(el),
      visible: isVisible(el),
      ...extra,
    });
  };

  for (const a of document.querySelectorAll('a[href]')) {
    const raw = a.getAttribute('href');
    if (!raw || raw.startsWith('javascript:')) continue;
    let url;
    try { url = new URL(raw, location.href); } catch (e) { continue; }
    if (['mailto:', 'tel:', 'sms:'].includes(url.protocol)) continue;
    if (a.hasAttribute('download') || /\.(pdf|zip|docx?|xlsx?|pptx?|csv|dmg|exe|apk)$/i.test(url.pathname)) {
      add(a, 'telechargement', { risk: 'telechargement' });
      continue;
    }
    if (url.origin !== origin) {
      links.push({ href: url.href, external: true, name: nameOf(a) });
      continue;
    }
    for (const [key, value] of url.searchParams) {
      params[key] = params[key] || [];
      if (!params[key].includes(value) && params[key].length < 12) params[key].push(value);
    }
    const samePage = url.pathname === location.pathname && url.search === location.search && url.hash;
    if (samePage || a.getAttribute('role') === 'button' || a.hasAttribute('aria-expanded') || a.getAttribute('role') === 'tab') {
      add(a, a.getAttribute('role') === 'tab' ? 'onglet' : (a.hasAttribute('aria-expanded') ? 'bascule' : 'ancre'));
    } else {
      links.push({ href: url.origin + url.pathname + url.search, external: false, name: nameOf(a) });
    }
  }

  for (const el of document.querySelectorAll('button, [role=button], input[type=button], input[type=submit], input[type=reset], summary, [role=tab], [role=switch], [role=menuitem], [role=menuitemcheckbox], [role=menuitemradio], [role=option], [role=combobox]')) {
    if (el.disabled) continue;
    const role = el.getAttribute('role');
    let kind = 'action';
    if (el.tagName === 'SUMMARY') kind = 'bascule';
    else if (role === 'tab') kind = 'onglet';
    else if (role === 'switch') kind = 'interrupteur';
    else if (role && role.startsWith('menuitem')) kind = 'element-menu';
    else if (role === 'option') kind = 'option';
    else if (role === 'combobox') kind = 'liste';
    else if (el.hasAttribute('aria-expanded') || el.hasAttribute('aria-haspopup') || el.hasAttribute('popovertarget') || el.hasAttribute('aria-controls')) kind = 'bascule';
    else if (el.type === 'submit' && (el.form || el.closest('form'))) kind = 'soumission';
    else if (el.type === 'reset') kind = 'reinitialisation';
    add(el, kind, {
      expanded: el.getAttribute('aria-expanded'),
      haspopup: el.getAttribute('aria-haspopup'),
      controls_id: el.getAttribute('aria-controls'),
    });
  }

  const fieldInfo = (el) => ({
    selector: selectorFor(el),
    tag: el.tagName.toLowerCase(),
    type: el.tagName === 'INPUT' ? (el.getAttribute('type') || 'text').toLowerCase() : el.tagName.toLowerCase(),
    name: el.name || el.id || '',
    label: nameOf(el),
    required: el.required || el.getAttribute('aria-required') === 'true',
    pattern: el.getAttribute('pattern'),
    min: el.getAttribute('min'),
    max: el.getAttribute('max'),
    step: el.getAttribute('step'),
    minlength: el.minLength > 0 ? el.minLength : null,
    maxlength: el.maxLength > 0 ? el.maxLength : null,
    autocomplete: el.getAttribute('autocomplete'),
    options: el.tagName === 'SELECT' ? [...el.options].filter((o) => !o.disabled).slice(0, 40).map((o) => ({ value: o.value, label: o.text.trim() })) : null,
    value: el.type === 'checkbox' || el.type === 'radio' ? el.value : null,
    visible: isVisible(el),
  });

  const fieldSelector = 'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=image]), select, textarea';
  for (const el of document.querySelectorAll(fieldSelector)) {
    if (el.disabled || el.readOnly) continue;
    const field = fieldInfo(el);
    const kind = field.type === 'checkbox' ? 'case' : field.type === 'radio' ? 'radio' : field.tag === 'select' ? 'liste' : field.type === 'range' ? 'curseur' : field.type === 'file' ? 'fichier' : 'champ';
    add(el, kind, { field, in_form: !!(el.form || el.closest('form')) });
  }

  const forms = [...document.querySelectorAll('form')].map((form) => {
    const submit = form.querySelector('[type=submit], button:not([type])');
    const method = (form.getAttribute('method') || 'get').toLowerCase();
    const action = form.getAttribute('action') || location.pathname;
    const name = form.getAttribute('aria-label') || (form.querySelector('legend, h1, h2, h3') ? textOf(form.querySelector('legend, h1, h2, h3')) : '') || form.id || '';
    const fields = [...form.querySelectorAll(fieldSelector)].filter((el) => !el.disabled && !el.readOnly).map(fieldInfo);
    const submitName = submit ? nameOf(submit) : '';
    return {
      selector: selectorFor(form),
      name,
      method,
      action,
      fields,
      submit: submit ? selectorFor(submit) : null,
      submit_name: submitName,
      risk: DESTRUCTIVE.test(`${submitName} ${name} ${action}`) ? 'destructif' : (method === 'get' ? 'sur' : 'mutation'),
      visible: isVisible(form),
    };
  });

  const alternates = [...document.querySelectorAll('link[rel=alternate][hreflang]')].map((l) => ({ hreflang: l.getAttribute('hreflang'), href: l.href }));
  const prefersDarkCss = [...document.styleSheets].some((sheet) => {
    try { return [...sheet.cssRules].some((r) => r.media && /prefers-color-scheme:\s*dark/.test(r.media.mediaText)); } catch (e) { return false; }
  });
  const breakpoints = new Set();
  for (const sheet of document.styleSheets) {
    let rules;
    try { rules = sheet.cssRules; } catch (e) { continue; }
    for (const rule of rules) {
      if (!rule.media) continue;
      for (const m of rule.media.mediaText.matchAll(/(min|max)-width:\s*(\d+(?:\.\d+)?)(px|em|rem)/g)) {
        const px = m[3] === 'px' ? parseFloat(m[2]) : parseFloat(m[2]) * 16;
        breakpoints.add(Math.round(px));
      }
    }
  }

  return {
    url: location.href,
    title: document.title,
    lang: document.documentElement.lang || null,
    controls,
    forms,
    links,
    params,
    alternates,
    supports_dark_scheme: prefersDarkCss,
    breakpoints: [...breakpoints].sort((a, b) => a - b),
  };
}
