(opts) => {
  const only = opts.only ? new Set(opts.only) : null;
  const wants = (name) => !only || only.has(name);
  const root = opts.scope ? document.querySelector(opts.scope) : document.body;
  if (!root) return { error: `Scope not found: ${opts.scope}` };

  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;
  const sx = window.scrollX;
  const sy = window.scrollY;
  const maxItems = opts.maxItems || 25;

  const INTERACTIVE = [
    'a[href]', 'button', 'input:not([type=hidden])', 'select', 'textarea', 'summary',
    '[role=button]', '[role=link]', '[role=checkbox]', '[role=radio]', '[role=switch]',
    '[role=tab]', '[role=menuitem]', '[role=option]', '[tabindex]:not([tabindex="-1"])',
    '[contenteditable=""]', '[contenteditable=true]',
  ].join(',');

  const cssPath = (el) => {
    if (!el || el.nodeType !== 1) return null;
    if (el.id && document.querySelectorAll(`#${CSS.escape(el.id)}`).length === 1) return `#${CSS.escape(el.id)}`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node !== document.documentElement && parts.length < 5) {
      let part = node.tagName.toLowerCase();
      if (node.id && document.querySelectorAll(`#${CSS.escape(node.id)}`).length === 1) {
        parts.unshift(`#${CSS.escape(node.id)}`);
        break;
      }
      const classes = [...node.classList].filter((c) => !c.startsWith('uiag')).slice(0, 2);
      if (classes.length) part += '.' + classes.map((c) => CSS.escape(c)).join('.');
      const parent = node.parentElement;
      if (parent) {
        const same = [...parent.children].filter((c) => c.tagName === node.tagName);
        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };

  const rectOf = (el) => el.getBoundingClientRect();
  const docBox = (r) => ({ x: Math.round(r.left + sx), y: Math.round(r.top + sy), w: Math.round(r.width), h: Math.round(r.height) });

  const isVisible = (el) => {
    const r = rectOf(el);
    if (r.width <= 1 || r.height <= 1) return false;
    if (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return false;
    const cs = getComputedStyle(el);
    if (cs.visibility !== 'visible' || parseFloat(cs.opacity) === 0) return false;
    return true;
  };

  const textOf = (n) => ((n && (n.innerText || n.textContent)) || '').replace(/\s+/g, ' ').trim();
  const ownText = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
  const hasOwnText = (el) => ownText(el).length > 0;

  const accName = (el) => {
    const labelledby = el.getAttribute('aria-labelledby');
    if (labelledby) {
      const t = labelledby.split(/\s+/).map((id) => document.getElementById(id)).filter(Boolean).map(textOf).join(' ').trim();
      if (t) return t;
    }
    const aria = (el.getAttribute('aria-label') || '').trim();
    if (aria) return aria;
    if (el.labels && el.labels.length) {
      const t = [...el.labels].map(textOf).join(' ').trim();
      if (t) return t;
    }
    if (el.matches('input[type=submit], input[type=button], input[type=reset]')) return (el.value || '').trim();
    if (el.matches('input[type=image], img, area')) return (el.getAttribute('alt') || '').trim();
    if (!el.matches('input, select, textarea')) {
      const t = textOf(el);
      if (t) return t;
      const inner = [...el.querySelectorAll('img[alt], svg title, [aria-label]')]
        .map((n) => n.getAttribute('alt') || n.getAttribute('aria-label') || n.textContent || '')
        .join(' ').trim();
      if (inner) return inner;
    }
    return (el.getAttribute('title') || '').trim();
  };

  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const toRgba = (value) => {
    if (!value || value === 'transparent') return { r: 0, g: 0, b: 0, a: 0 };
    const direct = value.match(/^rgba?\(([^)]+)\)$/);
    if (direct) {
      const p = direct[1].split(/[\s,/]+/).filter(Boolean).map((v) => (v.endsWith('%') ? parseFloat(v) / 100 : parseFloat(v)));
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    }
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = '#000';
    ctx.fillStyle = value;
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 };
  };
  const blend = (top, bottom) => {
    const a = top.a + bottom.a * (1 - top.a);
    if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
    return {
      r: (top.r * top.a + bottom.r * bottom.a * (1 - top.a)) / a,
      g: (top.g * top.a + bottom.g * bottom.a * (1 - top.a)) / a,
      b: (top.b * top.a + bottom.b * bottom.a * (1 - top.a)) / a,
      a,
    };
  };
  const luminance = (c) => {
    const ch = [c.r, c.g, c.b].map((v) => {
      const s = v / 255;
      return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  };
  const ratio = (a, b) => {
    const la = luminance(a);
    const lb = luminance(b);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  };
  const hex = (c) => '#' + [c.r, c.g, c.b].map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');

  const all = [...root.querySelectorAll('*')];
  const visibleCache = new Map();
  const visible = (el) => {
    if (!visibleCache.has(el)) visibleCache.set(el, isVisible(el));
    return visibleCache.get(el);
  };
  const interactive = [...root.querySelectorAll(INTERACTIVE)].filter((el) => visible(el) && !el.closest('[inert]'));
  const checks = {};

  if (wants('horizontal-overflow')) {
    const docWidth = document.documentElement.scrollWidth;
    const clipAncestor = (el) => {
      for (let a = el.parentElement; a && a !== document.documentElement; a = a.parentElement) {
        if (getComputedStyle(a).overflowX !== 'visible') return a;
      }
      return null;
    };
    const offenders = [];
    for (const el of all) {
      if (!visible(el)) continue;
      const r = rectOf(el);
      const cs = getComputedStyle(el);
      const beyondRight = r.right > vw + 1;
      const beyondLeft = r.left < -1 && cs.position !== 'fixed';
      if (!beyondRight && !beyondLeft) continue;
      const clip = clipAncestor(el);
      if (clip && clip !== document.body) continue;
      if (offenders.some((o) => o.el.contains(el))) continue;
      offenders.push({ el, r, clippedByBody: !!clip });
    }
    checks['horizontal-overflow'] = {
      controls: ['GEO-01', 'ACC-08'],
      result: docWidth > vw + 1 || offenders.length ? 'issues' : 'clean',
      page_scroll_width: docWidth,
      viewport_width: vw,
      causes_page_scroll: docWidth > vw + 1,
      items: offenders.slice(0, maxItems).map((o) => ({
        selector: cssPath(o.el),
        box: docBox(o.r),
        overflow_px: Math.round(Math.max(o.r.right - vw, -o.r.left)),
        kind: o.clippedByBody ? 'clipped-by-body' : 'exceeds-viewport',
      })),
    };
  }

  const renderedWithin = (node, container) => {
    for (let a = node.parentElement; a && a !== container; a = a.parentElement) {
      if (!visible(a)) return false;
      const cs = getComputedStyle(a);
      if (cs.clipPath && cs.clipPath.startsWith('inset(50%')) return false;
      if (cs.clip && /rect\(0(px)?,? 0(px)?,? 0(px)?,? 0(px)?\)/.test(cs.clip)) return false;
    }
    return true;
  };
  const textRects = (el, ownOnly) => {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let union = null;
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.textContent.trim()) continue;
      if (ownOnly) {
        let owner = node.parentElement;
        while (owner && owner !== el && ['inline', 'contents'].includes(getComputedStyle(owner).display)) owner = owner.parentElement;
        if (owner !== el) continue;
      }
      if (!renderedWithin(node, el)) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      for (const r of range.getClientRects()) {
        if (r.width < 0.5) continue;
        union = union
          ? { left: Math.min(union.left, r.left), right: Math.max(union.right, r.right), top: Math.min(union.top, r.top), bottom: Math.max(union.bottom, r.bottom) }
          : { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
      }
    }
    return union;
  };

  if (wants('text-overflow')) {
    const items = [];
    const isBounded = (el, cs) =>
      el.matches(INTERACTIVE) ||
      (toRgba(cs.backgroundColor).a > 0) ||
      parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.borderLeftWidth) > 0 ||
      cs.backgroundImage !== 'none';
    for (const el of all) {
      if (!visible(el)) continue;
      if (el.matches('input, select, textarea, svg, svg *, img, video, canvas, iframe')) continue;
      const interactiveEl = el.matches(INTERACTIVE);
      if (!hasOwnText(el) && !interactiveEl) continue;
      const cs = getComputedStyle(el);
      if (['inline', 'contents'].includes(cs.display)) continue;
      const clipX = cs.overflowX !== 'visible';
      const clipY = cs.overflowY !== 'visible';
      const scrollable = ['auto', 'scroll'].includes(cs.overflowX) || ['auto', 'scroll'].includes(cs.overflowY);
      if (scrollable && !interactiveEl) continue;
      if (!clipX && !clipY && !isBounded(el, cs)) continue;
      const union = textRects(el, !interactiveEl && !(clipX || clipY));
      if (!union) continue;
      const r = rectOf(el);
      const bl = parseFloat(cs.borderLeftWidth) || 0, br = parseFloat(cs.borderRightWidth) || 0;
      const bt = parseFloat(cs.borderTopWidth) || 0, bb = parseFloat(cs.borderBottomWidth) || 0;
      const inner = { left: r.left + bl, right: r.right - br, top: r.top + bt, bottom: r.bottom - bb };
      const intersects = union.right > inner.left && union.left < inner.right && union.bottom > inner.top && union.top < inner.bottom;
      if ((clipX || clipY) && !intersects) continue;
      const fontSize = parseFloat(cs.fontSize) || 16;
      const verticalSlack = Math.max(2, fontSize * 0.3);
      const overX = Math.max(union.right - inner.right, inner.left - union.left);
      const overY = Math.max(union.bottom - inner.bottom, inner.top - union.top);
      const horizontal = overX > 1;
      const vertical = overY > verticalSlack;
      if (!horizontal && !vertical) continue;
      const metrics = { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, text_overflow_x: Math.round(overX), text_overflow_y: Math.round(overY) };
      let kind;
      if ((horizontal && clipX) || (vertical && clipY)) {
        const fullText = el.getAttribute('title') || el.getAttribute('aria-label') || el.getAttribute('aria-describedby');
        const clamp = (cs.webkitLineClamp && cs.webkitLineClamp !== 'none') || (cs.lineClamp && cs.lineClamp !== 'none');
        const truncated = cs.textOverflow === 'ellipsis' || clamp;
        kind = truncated ? (fullText ? 'truncated-with-full-text' : 'truncated-without-full-text') : 'clipped';
      } else {
        kind = 'spills-out-of-box';
      }
      items.push({ selector: cssPath(el), text: textOf(el).slice(0, 80), box: docBox(r), kind, interactive: interactiveEl, metrics });
    }
    const blocking = items.filter((i) => i.kind === 'clipped' || i.kind === 'spills-out-of-box' || (i.kind === 'truncated-without-full-text' && i.interactive));
    items.forEach((i) => { i.candidate = blocking.includes(i); });
    items.sort((a, b) => Number(b.candidate) - Number(a.candidate));
    checks['text-overflow'] = {
      controls: ['GEO-03', 'CTA-01', 'TXT-08', 'LOC-01', 'TXT-04'],
      result: blocking.length ? 'issues' : 'clean',
      note: 'Intentional truncation (ellipsis, line-clamp) outside actions: listed, not blocking, judge against the need to read the full text.',
      items: items.slice(0, maxItems),
      total: items.length,
    };
  }

  if (wants('occlusion')) {
    const items = [];
    const modal = [...document.querySelectorAll('dialog, [aria-modal=true]')].reverse().find((d) => {
      try { if (d.matches(':modal')) return true; } catch (e) { }
      return d.getAttribute('aria-modal') === 'true' && visible(d);
    });
    const layerOf = (node) => {
      for (let a = node; a && a !== document.documentElement; a = a.parentElement) {
        const position = getComputedStyle(a).position;
        if (['fixed', 'sticky', 'absolute'].includes(position)) return a === node ? position : `${position} via ${cssPath(a)}`;
      }
      return 'static';
    };
    const ownLabel = (hit, el) => {
      const label = hit.closest && hit.closest('label');
      return !!label && label.control === el;
    };
    const openOverlays = [
      ...[...document.querySelectorAll('[aria-expanded=true][aria-controls]')].flatMap((t) => t.getAttribute('aria-controls').split(/\s+/).map((id) => document.getElementById(id))),
      ...document.querySelectorAll('[role=menu], [role=listbox], [role=tooltip], dialog[open]'),
      ...(() => { try { return [...document.querySelectorAll(':popover-open')]; } catch (e) { return []; } })(),
    ].filter((n) => n && visible(n));
    const insideOpenOverlay = (node) => openOverlays.some((o) => o.contains(node));
    for (const el of interactive) {
      if (modal && !modal.contains(el)) continue;
      const r = [...el.getClientRects()].reduce((best, cur) => (cur.width * cur.height > best.width * best.height ? cur : best), rectOf(el).width && getComputedStyle(el).display !== 'inline' ? rectOf(el) : { width: 0, height: 0 });
      if (!r.width || r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) continue;
      const cs = getComputedStyle(el);
      if (cs.pointerEvents === 'none') continue;
      const points = [[0.5, 0.5], [0.15, 0.15], [0.85, 0.15], [0.15, 0.85], [0.85, 0.85]]
        .map(([fx, fy]) => ({ x: r.left + r.width * fx, y: r.top + r.height * fy, center: fx === 0.5 }))
        .filter((p) => p.x >= 0 && p.y >= 0 && p.x < vw && p.y < vh);
      if (!points.length) continue;
      let blockedCenter = false;
      let blockedCount = 0;
      let occluder = null;
      let behindAncestor = false;
      for (const p of points) {
        const hit = document.elementFromPoint(p.x, p.y);
        const ok = !!hit && (hit === el || el.contains(hit) || ownLabel(hit, el));
        if (ok) continue;
        if (hit && hit.contains(el)) { behindAncestor = true; continue; }
        if (hit && insideOpenOverlay(hit) && !insideOpenOverlay(el)) continue;
        blockedCount += 1;
        if (p.center) blockedCenter = true;
        if (!occluder && hit) occluder = hit;
      }
      const centerVisible = points.some((p) => p.center);
      const fully = r.top >= 0 && r.bottom <= vh && r.left >= 0 && r.right <= vw;
      items.push({
        selector: cssPath(el),
        name: accName(el).slice(0, 60),
        box: docBox(r),
        fully_in_viewport: fully,
        center_in_viewport: centerVisible,
        state: blockedCenter ? 'center-covered' : blockedCount ? 'partially-covered' : 'clear',
        occluder: occluder ? cssPath(occluder) : null,
        occluder_position: occluder ? layerOf(occluder) : null,
        behind_ancestor: behindAncestor,
      });
    }
    const problems = items.filter((i) => i.state !== 'clear');
    checks.occlusion = {
      controls: ['STK-01', 'STK-06'],
      result: problems.some((i) => i.state === 'center-covered') ? 'issues' : 'clean',
      scroll_y: sy,
      items: opts.allOcclusion ? items : problems.slice(0, maxItems),
      partial: problems.filter((i) => i.state === 'partially-covered').length,
    };
  }

  if (wants('target-size')) {
    const min = opts.minTarget || 24;
    const touch = opts.touchTarget || 0;
    const targets = interactive.map((el) => {
      let r = rectOf(el);
      if (el.matches('input[type=checkbox], input[type=radio]') && el.labels && el.labels.length) {
        for (const label of el.labels) {
          const lr = rectOf(label);
          if (lr.width && lr.height) {
            r = { left: Math.min(r.left, lr.left), right: Math.max(r.right, lr.right), top: Math.min(r.top, lr.top), bottom: Math.max(r.bottom, lr.bottom) };
            r.width = r.right - r.left;
            r.height = r.bottom - r.top;
          }
        }
      }
      return { el, r };
    }).filter((t) => !t.el.parentElement || !t.el.parentElement.closest(INTERACTIVE));
    const inlineInText = (el) => {
      if (getComputedStyle(el).display !== 'inline') return false;
      const block = el.closest('p, li, td, dd, blockquote, label, figcaption');
      return !!block && textOf(block).length > textOf(el).length + 5;
    };
    const distToRect = (cx, cy, r) => {
      const dx = Math.max(r.left - cx, 0, cx - r.right);
      const dy = Math.max(r.top - cy, 0, cy - r.bottom);
      return Math.hypot(dx, dy);
    };
    const items = [];
    const warnings = [];
    for (const t of targets) {
      const { el, r } = t;
      const small = r.width < min || r.height < min;
      if (small && !inlineInText(el) && !el.matches('input[type=range]')) {
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        let conflict = null;
        for (const o of targets) {
          if (o === t || o.el.contains(el) || el.contains(o.el)) continue;
          const oSmall = o.r.width < min || o.r.height < min;
          const ocx = o.r.left + o.r.width / 2;
          const ocy = o.r.top + o.r.height / 2;
          if (distToRect(cx, cy, o.r) < min / 2 || (oSmall && Math.hypot(cx - ocx, cy - ocy) < min)) {
            conflict = o.el;
            break;
          }
        }
        const entry = { selector: cssPath(el), name: accName(el).slice(0, 60), box: docBox(r), size: [Math.round(r.width), Math.round(r.height)] };
        if (conflict) items.push({ ...entry, kind: 'too-small-and-too-close', neighbor: cssPath(conflict) });
        else warnings.push({ ...entry, kind: 'below-minimum-but-spaced' });
      } else if (touch && (r.width < touch || r.height < touch) && !inlineInText(el)) {
        warnings.push({ selector: cssPath(el), name: accName(el).slice(0, 60), box: docBox(r), size: [Math.round(r.width), Math.round(r.height)], kind: `below-touch-guideline-${touch}px` });
      }
    }
    checks['target-size'] = {
      controls: ['CTA-03'],
      result: items.length ? 'issues' : 'clean',
      minimum: min,
      touch_guideline: touch || null,
      items: items.slice(0, maxItems),
      warnings: warnings.slice(0, maxItems),
    };
  }

  if (wants('alignment')) {
    const tol = opts.alignTolerance ?? 1;
    const items = [];
    const parents = new Set(interactive.map((el) => el.parentElement).filter(Boolean));
    for (const el of interactive) {
      const p = el.parentElement && el.parentElement.parentElement;
      if (p && el.parentElement.children.length === 1) parents.add(p);
    }
    const median = (arr) => {
      const s = [...arr].sort((a, b) => a - b);
      return s[Math.floor(s.length / 2)];
    };
    const analyse = (group, axis) => {
      if (group.length < 2) return;
      const edges = axis === 'row'
        ? group.map((k) => ({ k, a: k.r.top, c: k.r.top + k.r.height / 2, b: k.r.bottom, size: k.r.height }))
        : group.map((k) => ({ k, a: k.r.left, c: k.r.left + k.r.width / 2, b: k.r.right, size: k.r.width }));
      const ma = median(edges.map((e) => e.a));
      const mc = median(edges.map((e) => e.c));
      const mb = median(edges.map((e) => e.b));
      const outliers = edges.filter((e) => Math.min(Math.abs(e.a - ma), Math.abs(e.c - mc), Math.abs(e.b - mb)) > tol);
      if (!outliers.length || outliers.length > group.length / 2) return;
      if (group.length === 2) {
        const sizes = edges.map((e) => e.size);
        if (Math.abs(sizes[0] - sizes[1]) > Math.max(sizes[0], sizes[1]) * 0.2) return;
      }
      for (const o of outliers) {
        items.push({
          selector: cssPath(o.k.el),
          box: docBox(o.k.r),
          axis: axis === 'row' ? 'row (top, center, bottom)' : 'column (left, center, right)',
          offset_px: Math.round(Math.min(Math.abs(o.a - ma), Math.abs(o.c - mc), Math.abs(o.b - mb))),
          group: cssPath(o.k.el.parentElement),
          group_size: group.length,
          confidence: group.length >= 3 ? 'medium' : 'low',
        });
      }
    };
    for (const parent of parents) {
      const kids = [...parent.children]
        .filter((k) => visible(k))
        .map((k) => ({ el: k, r: rectOf(k), cs: getComputedStyle(k) }))
        .filter((k) => !['absolute', 'fixed'].includes(k.cs.position) && k.cs.display !== 'inline' && k.cs.float === 'none');
      if (kids.length < 2 || kids.length > 24) continue;
      const rows = [];
      for (const k of kids) {
        const row = rows.find((g) => g.some((o) => {
          const overlap = Math.min(o.r.bottom, k.r.bottom) - Math.max(o.r.top, k.r.top);
          return overlap > Math.min(o.r.height, k.r.height) * 0.5;
        }));
        if (row) row.push(k); else rows.push([k]);
      }
      rows.filter((g) => g.length >= 2).forEach((g) => analyse(g, 'row'));
      const cols = [];
      for (const k of kids) {
        const col = cols.find((g) => g.some((o) => {
          const overlap = Math.min(o.r.right, k.r.right) - Math.max(o.r.left, k.r.left);
          return overlap > Math.min(o.r.width, k.r.width) * 0.5;
        }));
        if (col) col.push(k); else cols.push([k]);
      }
      cols.filter((g) => g.length >= 3).forEach((g) => analyse(g, 'col'));
    }
    checks.alignment = {
      controls: ['GEO-02', 'CTA-02', 'CTA-04'],
      result: items.length ? 'issues' : 'clean',
      tolerance_px: tol,
      note: 'Heuristic: confirm on the screenshot and against the design system.',
      items: items.slice(0, maxItems),
    };
  }

  if (wants('contrast')) {
    const items = [];
    const assisted = [];
    const seen = new Set();
    for (const el of all) {
      if (!visible(el) || !hasOwnText(el)) continue;
      if (el.closest('[disabled], [aria-disabled=true], :disabled')) continue;
      const ownRects = textRects(el, true);
      const elRect = rectOf(el);
      if (!ownRects || ownRects.right < elRect.left || ownRects.left > elRect.right || ownRects.bottom < elRect.top || ownRects.top > elRect.bottom) continue;
      const cs = getComputedStyle(el);
      let fg = toRgba(cs.color);
      let bg = { r: 0, g: 0, b: 0, a: 0 };
      let complex = null;
      for (let node = el; node; node = node.parentElement) {
        const ncs = getComputedStyle(node);
        if (ncs.backgroundImage && ncs.backgroundImage !== 'none') { complex = 'image-or-gradient'; break; }
        const layer = toRgba(ncs.backgroundColor);
        if (layer.a > 0) bg = blend(bg, layer);
        if (bg.a >= 0.999) break;
      }
      if (!complex && bg.a < 0.999) bg = blend(bg, { r: 255, g: 255, b: 255, a: 1 });
      if (complex) {
        if (assisted.length < maxItems) assisted.push({ selector: cssPath(el), text: ownText(el).slice(0, 60), reason: complex });
        continue;
      }
      if (fg.a < 1) fg = blend(fg, bg);
      const size = parseFloat(cs.fontSize);
      const weight = parseInt(cs.fontWeight, 10) || 400;
      const large = size >= 24 || (size >= 18.66 && weight >= 700);
      const required = large ? 3 : 4.5;
      const value = ratio(fg, bg);
      if (value + 0.005 < required) {
        const key = `${hex(fg)}|${hex(bg)}|${cssPath(el)}`;
        if (seen.has(key)) continue;
        seen.add(key);
        items.push({
          selector: cssPath(el),
          text: ownText(el).slice(0, 60),
          box: docBox(rectOf(el)),
          ratio: Math.round(value * 100) / 100,
          required,
          color: hex(fg),
          background: hex(bg),
          font: `${size}px/${weight}`,
        });
      }
    }
    checks.contrast = {
      controls: ['TXT-01'],
      result: items.length ? 'issues' : 'clean',
      thresholds: 'Reference WCAG 2.2 SC 1.4.3 (4.5:1, 3:1 large text), to confirm for the project',
      items: items.slice(0, maxItems),
      needs_assisted: assisted,
      total: items.length,
    };
  }

  const fieldSelector = 'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=image]), select, textarea';
  const fields = [...root.querySelectorAll(fieldSelector)].filter((el) =>
    !el.closest('[inert]') && (!el.checkVisibility || el.checkVisibility({ visibilityProperty: true })) && getComputedStyle(el).display !== 'none');

  if (wants('form-labels')) {
    const items = [];
    for (const el of fields) {
      const name = accName(el);
      const visibleLabel = (el.labels && [...el.labels].some((l) => visible(l) && textOf(l))) ||
        (el.getAttribute('aria-labelledby') || '').split(/\s+/).some((id) => { const n = document.getElementById(id); return n && visible(n) && textOf(n); });
      if (!name) {
        items.push({ selector: cssPath(el), box: docBox(rectOf(el)), kind: el.placeholder ? 'placeholder-only' : 'no-accessible-name' });
      } else if (!visibleLabel && el.placeholder && visible(el)) {
        items.push({ selector: cssPath(el), box: docBox(rectOf(el)), kind: 'no-visible-label', name });
      }
    }
    checks['form-labels'] = { controls: ['FRM-01'], result: items.length ? 'issues' : 'clean', fields: fields.length, items: items.slice(0, maxItems) };
  }

  if (wants('accessible-names')) {
    const items = [];
    for (const el of interactive) {
      if (el.matches(fieldSelector)) continue;
      if (!accName(el)) items.push({ selector: cssPath(el), box: docBox(rectOf(el)), role: el.getAttribute('role') || el.tagName.toLowerCase() });
    }
    checks['accessible-names'] = {
      controls: ['ACC-05'],
      result: items.length ? 'issues' : 'clean',
      note: 'Empty names only; approximate name, confirm with aria-snapshot.',
      items: items.slice(0, maxItems),
    };
  }

  if (wants('form-errors')) {
    const errorPattern = /(erreur|invalide|obligatoire|requis|incorrect|manquant|error|invalid|required|missing|must be|mandatory)/i;
    const describedIds = new Set();
    for (const f of fields) {
      for (const attr of ['aria-describedby', 'aria-errormessage']) {
        (f.getAttribute(attr) || '').split(/\s+/).filter(Boolean).forEach((id) => describedIds.add(id));
      }
    }
    const linked = [...describedIds].map((id) => document.getElementById(id)).filter(Boolean);
    const items = [];
    const announcedSummaries = [];
    for (const el of all) {
      if (!visible(el) || !hasOwnText(el)) continue;
      const text = ownText(el);
      if (text.length > 300 || !errorPattern.test(text)) continue;
      if (el.closest('label, legend, button, a, h1, h2, h3, h4, h5, h6, th, [data-uiag-ignore]')) continue;
      const isLinked = linked.some((l) => l === el || l.contains(el) || el.contains(l));
      const live = el.closest('[role=alert], [role=status], [aria-live]:not([aria-live=off]), output');
      if (isLinked) continue;
      if (live) {
        announcedSummaries.push({ selector: cssPath(el), text: text.slice(0, 80), kind: 'announced-summary', links_to_fields: !!live.querySelector('a[href^="#"]') });
      } else {
        items.push({ selector: cssPath(el), text: text.slice(0, 80), box: docBox(rectOf(el)), kind: 'unlinked-unannounced-message' });
      }
    }
    for (const f of fields) {
      if (f.getAttribute('aria-invalid') === 'true') {
        const ids = [...(f.getAttribute('aria-describedby') || '').split(/\s+/), ...(f.getAttribute('aria-errormessage') || '').split(/\s+/)].filter(Boolean);
        const hasMessage = ids.some((id) => { const n = document.getElementById(id); return n && textOf(n); });
        if (!hasMessage) items.push({ selector: cssPath(f), box: docBox(rectOf(f)), kind: 'aria-invalid-without-message' });
      }
    }
    checks['form-errors'] = {
      controls: ['FRM-03', 'ACC-06'],
      result: items.length ? 'issues' : 'clean',
      note: 'Useful after an action that triggers an error. Message proximity and clarity: visual review.',
      invalid_fields: fields.filter((f) => f.getAttribute('aria-invalid') === 'true').length,
      items: items.slice(0, maxItems),
      announced_summaries: announcedSummaries,
    };
  }

  if (wants('images')) {
    const items = [];
    for (const img of root.querySelectorAll('img')) {
      if (!img.hasAttribute('alt') && !img.closest('[aria-hidden=true]') && img.getAttribute('role') !== 'presentation') {
        items.push({ selector: cssPath(img), kind: 'missing-alt', src: (img.currentSrc || img.src || '').slice(0, 160) });
      }
      if (img.complete && img.naturalWidth === 0 && (img.currentSrc || img.src)) {
        items.push({ selector: cssPath(img), kind: 'broken-image', src: (img.currentSrc || img.src || '').slice(0, 160) });
      } else if (img.naturalWidth && visible(img)) {
        const r = rectOf(img);
        const fit = getComputedStyle(img).objectFit;
        const natural = img.naturalWidth / img.naturalHeight;
        const shown = r.width / r.height;
        if (['fill', ''].includes(fit) && Math.abs(natural - shown) / natural > 0.05) {
          items.push({ selector: cssPath(img), kind: 'distorted-image', natural_ratio: Math.round(natural * 100) / 100, displayed_ratio: Math.round(shown * 100) / 100, box: docBox(r) });
        }
      }
    }
    for (const el of root.querySelectorAll('[role=img]')) {
      if (!accName(el) && !el.closest('[aria-hidden=true]')) items.push({ selector: cssPath(el), kind: 'role-img-without-name' });
    }
    checks.images = { controls: ['COL-05', 'COL-04'], result: items.length ? 'issues' : 'clean', items: items.slice(0, maxItems) };
  }

  if (wants('headings')) {
    const heads = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6, [role=heading]')]
      .filter((h) => visible(h) || (h.checkVisibility && h.checkVisibility()))
      .map((h) => ({ el: h, level: h.getAttribute('aria-level') ? parseInt(h.getAttribute('aria-level'), 10) : parseInt(h.tagName.slice(1), 10) || 2 }));
    const items = [];
    let previous = 0;
    for (const h of heads) {
      if (previous && h.level > previous + 1) items.push({ selector: cssPath(h.el), text: textOf(h.el).slice(0, 60), kind: `skip-h${previous}-to-h${h.level}` });
      previous = h.level;
    }
    const h1 = heads.filter((h) => h.level === 1).length;
    if (h1 === 0) items.push({ kind: 'no-h1' });
    checks.headings = {
      controls: ['TXT-02'],
      result: items.length ? 'issues' : 'clean',
      outline: heads.slice(0, 40).map((h) => `h${h.level} ${textOf(h.el).slice(0, 50)}`),
      h1_count: h1,
      items,
    };
  }

  if (wants('document')) {
    const items = [];
    if (!document.title.trim()) items.push({ kind: 'empty-title' });
    const lang = document.documentElement.getAttribute('lang');
    if (!lang) items.push({ kind: 'missing-lang' });
    checks.document = { controls: ['NAV-01', 'ACC-12'], result: items.length ? 'issues' : 'clean', title: document.title, lang, items };
  }

  if (wants('landmarks')) {
    const mains = document.querySelectorAll('main, [role=main]').length;
    const skip = [...document.querySelectorAll('a[href^="#"]')].slice(0, 3).find((a) => {
      const target = document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
      return target && (target.matches('main, [role=main]') || target.closest('main, [role=main]'));
    });
    const items = [];
    if (mains !== 1) items.push({ kind: `main-${mains}` });
    if (!skip) items.push({ kind: 'missing-skip-link' });
    checks.landmarks = { controls: ['ACC-10'], result: items.length ? 'issues' : 'clean', items };
  }

  return { viewport: { width: vw, height: vh }, scroll: { x: sx, y: sy }, document_height: document.documentElement.scrollHeight, checks };
}
