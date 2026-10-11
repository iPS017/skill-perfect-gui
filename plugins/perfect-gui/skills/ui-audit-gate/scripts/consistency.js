() => {
  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;
  const isVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) return false;
    if (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return false;
    return true;
  };
  const pathOf = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    for (let n = el; n && n.nodeType === 1 && n !== document.documentElement && parts.length < 4; n = n.parentElement) {
      let part = n.tagName.toLowerCase();
      if (n.id) { parts.unshift('#' + CSS.escape(n.id)); break; }
      const cls = [...n.classList].slice(0, 2);
      if (cls.length) part += '.' + cls.map((c) => CSS.escape(c)).join('.');
      parts.unshift(part);
    }
    return parts.join(' > ');
  };
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const rgba = (value) => {
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = 'rgba(0,0,0,0)';
    ctx.fillStyle = value;
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 };
  };
  const luminance = (c) => {
    const ch = [c.r, c.g, c.b].map((v) => { const s = v / 255; return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4); });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  };
  const effectiveBackground = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const c = rgba(getComputedStyle(n).backgroundColor);
      if (c.a > 0.9) return c;
    }
    return { r: 255, g: 255, b: 255, a: 1 };
  };

  const roles = {
    button: { selector: 'button, [role=button], input[type=submit], input[type=button], a[class*=btn], a[class*=button]', props: ['fontFamily', 'fontSize', 'fontWeight', 'borderTopLeftRadius', 'textTransform'] },
    field: { selector: 'input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=range]):not([type=submit]):not([type=button]), select, textarea', props: ['fontFamily', 'fontSize', 'borderTopLeftRadius', 'borderTopWidth'] },
    link: { selector: 'main p a[href], main li a[href]:not([class*=btn]):not([class*=button])', props: ['color', 'textDecorationLine', 'fontFamily'] },
    h1: { selector: 'h1', props: ['fontFamily', 'fontSize', 'fontWeight'] },
    h2: { selector: 'h2', props: ['fontFamily', 'fontSize', 'fontWeight'] },
    h3: { selector: 'h3', props: ['fontFamily', 'fontSize', 'fontWeight'] },
    text: { selector: 'main p', props: ['fontFamily', 'fontSize', 'lineHeight'] },
  };
  const styles = {};
  for (const [role, spec] of Object.entries(roles)) {
    styles[role] = [...document.querySelectorAll(spec.selector)].filter(isVisible).slice(0, 40).map((el) => {
      const cs = getComputedStyle(el);
      const signature = {};
      for (const p of spec.props) signature[p] = cs[p];
      return { selector: pathOf(el), signature };
    });
  }

  const families = new Map();
  for (const el of document.querySelectorAll('body, body *')) {
    if (!isVisible(el)) continue;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const first = getComputedStyle(el).fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '');
    if (!families.has(first)) families.set(first, pathOf(el));
  }
  const generic = /^(serif|sans-serif|monospace|cursive|fantasy|system-ui|ui-sans-serif|ui-serif|ui-monospace|ui-rounded|emoji|math|fangsong|-apple-system|BlinkMacSystemFont)$/i;
  const declared = new Set([...(document.fonts || [])].map((f) => f.family.replace(/^["']|["']$/g, '')));
  const fonts = [...families.entries()].map(([family, sample]) => ({
    family,
    sample,
    webfont: declared.has(family),
    loaded: generic.test(family) || !declared.has(family) ? null : [...document.fonts].some((f) => f.family.replace(/^["']|["']$/g, '') === family && f.status === 'loaded'),
  }));

  const bodyBg = effectiveBackground(document.body);
  const pageDark = luminance(bodyBg) < 0.2;
  const lightIslands = [];
  if (pageDark) {
    for (const el of document.querySelectorAll('body *')) {
      if (!isVisible(el) || el.matches('img, video, canvas, svg, svg *, iframe, picture, [role=img]')) continue;
      const c = rgba(getComputedStyle(el).backgroundColor);
      if (c.a < 0.9 || luminance(c) < 0.75) continue;
      const r = el.getBoundingClientRect();
      if ((r.width * r.height) / (vw * vh) < 0.02) continue;
      if (lightIslands.some((x) => x.el.contains(el))) continue;
      lightIslands.push({ el, box: { x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) } });
    }
  }

  const openDialogs = [...document.querySelectorAll('dialog[open], [aria-modal=true], [role=dialog]:not([hidden])')].filter(isVisible).length;
  const htmlStyle = getComputedStyle(document.documentElement);
  const bodyStyle = getComputedStyle(document.body);
  const scrollLocked = !openDialogs && (bodyStyle.overflowY === 'hidden' || htmlStyle.overflowY === 'hidden' || bodyStyle.position === 'fixed')
    && document.documentElement.scrollHeight > vh + 4;

  const texts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.textContent.trim().length > 3 && /\p{L}{3,}/u.test(n.textContent) && !n.parentElement.closest('script, style, noscript, code, pre') ? 1 : 2),
  });
  while (walker.nextNode() && texts.length < 400) {
    const parent = walker.currentNode.parentElement;
    if (parent && isVisible(parent)) texts.push(walker.currentNode.textContent.replace(/\s+/g, ' ').trim());
  }

  return {
    lang: document.documentElement.lang || null,
    theme: { page_dark: pageDark, body_background: `rgb(${bodyBg.r},${bodyBg.g},${bodyBg.b})`, prefers_dark: matchMedia('(prefers-color-scheme: dark)').matches, light_islands: lightIslands.slice(0, 10).map((x) => ({ selector: pathOf(x.el), box: x.box })) },
    fonts,
    scroll_locked: scrollLocked,
    open_dialogs: openDialogs,
    styles,
    texts,
  };
}
