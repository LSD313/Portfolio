/* ============================================================
   The Votive Wheel — implementation of Seeklore Slots.dc.html

   The source is a Claude Design canvas: its markup carries inline
   styles and {{ }} bindings, <sc-for>/<sc-if> control flow and a
   DCLogic class, all resolved at runtime by support.js. Here the
   template is ported to React.createElement and the bindings are
   resolved at author time; the game logic is carried across
   essentially verbatim from the canvas so behaviour matches.

   React is used rather than string rendering because the flying
   worshippers animate by transitioning the *same* elements between
   phases — that needs keyed reconciliation, not innerHTML.
   ============================================================ */
(function () {
  'use strict';
  var h = React.createElement;

  /* ---- design-system Button, reproduced from _ds_bundle.js ---- */
  function Button(p) {
    var hoverState = React.useState(false), hover = hoverState[0], setHover = hoverState[1];
    var sizes = { sm: { padding: '6px 12px', fontSize: 13, gap: 6 }, md: { padding: '9px 18px', fontSize: 14, gap: 8 } };
    var s = sizes[p.size] || sizes.md;
    var disabled = !!p.disabled;
    var base = {
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      gap: s.gap, padding: s.padding, fontFamily: 'var(--font-ui)', fontSize: s.fontSize,
      fontWeight: 500, lineHeight: 1, borderRadius: 'var(--radius-md)',
      cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
      transition: 'background var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out)',
      border: '1px solid transparent', minHeight: p.size === 'sm' ? 32 : 44, boxSizing: 'border-box'
    };
    var variants = {
      primary: {
        background: hover && !disabled ? 'var(--place-hover)' : 'var(--place-base)',
        color: '#fff', boxShadow: hover && !disabled ? 'var(--shadow-md)' : 'var(--shadow-sm)'
      },
      secondary: {
        background: 'var(--surface-raised)', color: 'var(--text-primary)',
        borderColor: hover && !disabled ? 'var(--border-strong)' : 'var(--border-medium)',
        boxShadow: hover && !disabled ? 'var(--shadow-sm)' : 'none'
      }
    };
    return h('button', {
      type: 'button', disabled: disabled, onClick: p.onClick,
      onMouseEnter: function () { setHover(true); }, onMouseLeave: function () { setHover(false); },
      style: Object.assign({}, base, variants[p.variant] || variants.primary)
    }, p.children);
  }

  /* ---- DCLogic shim: what support.js provided the canvas ---- */
  function DCLogic() {}
  DCLogic.prototype.setState = function (patch) {
    this.state = Object.assign({}, this.state, typeof patch === 'function' ? patch(this.state) : patch);
    if (this._sub) this._sub();
  };

  /* =========================================================
     Game logic — carried across from the canvas
     ========================================================= */
  function Component(props) {
    this.props = props || {};
    this.state = {
      balance: null, bet: 100, spinning: false,
      pos: [0, 0, 0, 0, 0], blur: [false, false, false, false, false], hit: [false, false, false, false, false],
      msg: 'Place a stake and spin. The gods are listening.',
      win: 0, lastWin: 0, modal: null, bonus: null,
      charted: [false, false, false], placeM: [0, 0, 0], thr: [0, 0, 0],
      sessionStart: Date.now(), spins: 0, staked: 0, won: 0, rcShown: 0
    };
  }
  Component.prototype = Object.create(DCLogic.prototype);
  Component.prototype.constructor = Component;

  // Tuned config — keep in sync with the canvas (and sim/harness.js SlotSim.config)
  Component.prototype.CFG = {
    payRealm: { 3: 10, 4: 50, 5: 200 }, payConf: 6,
    payItem: { 3: 5, 4: 12, 5: 35 }, payOff: { 3: 3, 4: 8, 5: 20 },
    payMixed3: 0.4, payGodPair: 0.4, payOffPair: 0.3, payItemPair: 0.2,
    mortalBase: 10, stakeRef: 100, boons: [0.25, 0.5, 0.75, 1], bonusWorGain: [2, 4], bonusItemM: 2, bonusPlaceM: 4,
    payPerMortal: 5, minRiteSpins: 3, thr: [100, 1000]
  };
  Component.prototype.fmt = function (n) { return n.toLocaleString(); };
  Component.prototype.balNow = function () {
    return this.state.balance == null ? (this.props.startingWorship != null ? this.props.startingWorship : 2000) : this.state.balance;
  };
  Component.prototype.rint = function (a, b) { return a + Math.floor(Math.random() * (b - a + 1)); };
  Component.prototype.rollThr = function () {
    var t = this.CFG.thr; return [this.rint(t[0], t[1]), this.rint(t[0], t[1]), this.rint(t[0], t[1])];
  };
  Component.prototype.shuffle = function (a, seed) {
    var s = a.slice(), x = seed, i, j, tmp;
    for (i = s.length - 1; i > 0; i--) { x = (x * 9301 + 49297) % 233280; j = x % (i + 1); tmp = s[i]; s[i] = s[j]; s[j] = tmp; }
    return s;
  };
  Component.prototype.buildData = function () {
    var self = this;
    this.PLACES = [
      { id: 'the-basalt-causeway', name: 'The Basalt Causeway', realm: 'P', img: 'symbols-web/place-the-basalt-causeway.png' },
      { id: 'the-elder-grove', name: 'The Elder Grove', realm: 'L', img: 'symbols-web/place-the-elder-grove.png' },
      { id: 'the-wayside-hearth', name: 'The Wayside Hearth', realm: 'S', img: 'symbols-web/place-the-wayside-hearth.png' }
    ];
    var g = function (id, realm) { return { t: 'god', id: id, realm: realm, img: 'symbols-web/god-' + id + '.png' }; };
    var it = function (id) { return { t: 'item', id: id, img: 'symbols-web/item-' + id + '.png' }; };
    var off = { t: 'off', id: 'offering', img: 'symbols-web/power-offering.png' };
    var wor = { t: 'wor', img: 'symbols-web/worshippers-1.png' };
    var quiet = { t: 'quiet' };
    var reelGods = [
      [g('neptune', 'P'), g('gaia', 'L'), g('nike', 'S')],
      [g('raiden', 'P'), g('demeter', 'L'), g('eris', 'S')],
      [g('vulcan', 'P'), g('pan', 'L'), g('hestia', 'S')],
      [g('helios', 'P'), g('artemis', 'L'), g('anansi', 'S')],
      [g('skadi', 'P'), g('osiris', 'L'), g('morpheus', 'S')]
    ];
    var items = ['pilgrim-s-blade', 'votive-charm', 'prayer-beads', 'war-banner', 'censer-of-devotion', 'relic-shard'];
    this.strips = reelGods.map(function (gs, r) {
      var s = gs.slice();
      items.forEach(function (i) { s.push(it(i)); });
      s.push(off, off);
      s.push({ t: 'place', pIdx: r % 3, img: self.PLACES[r % 3].img });
      s.push({ t: 'place', pIdx: (r + 1) % 3, img: self.PLACES[(r + 1) % 3].img });
      s.push(wor, wor);
      s.push(quiet, quiet, quiet);
      return self.shuffle(s, 7 + r * 3);
    });
    var bItems = ['censer-of-devotion', 'relic-shard', 'prayer-beads', 'votive-charm'];
    this.bStrips = [0, 1, 2, 3, 4].map(function (r) {
      var s = [1, 2, 3].map(function (n) { return { t: 'wor', n: n, img: 'symbols-web/worshippers-' + n + '.png' }; });
      bItems.forEach(function (i) { s.push({ t: 'item', id: i, img: 'symbols-web/item-' + i + '.png' }); });
      s.push({ t: 'place', pIdx: r % 3, img: self.PLACES[r % 3].img });
      s.push({ t: 'place', pIdx: (r + 1) % 3, img: self.PLACES[(r + 1) % 3].img });
      for (var k = 0; k < 3; k++) s.push({ t: 'quiet' });
      return self.shuffle(s, 5 + r);
    });
    this.allImgs = ['symbols-web/panorama-pilgrim-coast.jpg'];
    this.strips.concat(this.bStrips).forEach(function (s) {
      s.forEach(function (sym) { if (sym.img && self.allImgs.indexOf(sym.img) < 0) self.allImgs.push(sym.img); });
    });
  };
  Component.prototype.stepBet = function (d) {
    var B = [25, 50, 100, 250, 500];
    var i = Math.max(0, Math.min(B.length - 1, B.indexOf(this.state.bet) + d));
    if (!this.state.spinning) this.setState({ bet: B[i] });
  };
  Component.prototype.addCoins = function () { this.setState({ balance: this.balNow() + 2000 }); };
  Component.prototype.spin = function () {
    var self = this;
    if (this.state.spinning || this.state.bonus || this.state.fanfare) return;
    var bet = this.state.bet, bal = this.balNow();
    if (bal < bet) return;
    var stops = this.strips.map(function (s) { return Math.floor(Math.random() * s.length); });
    var fast = this.props.fastSpins;
    var thr = this.state.thr[0] === 0 ? this.rollThr() : this.state.thr;
    this.setState({
      balance: bal - bet, staked: this.state.staked + bet, spins: this.state.spins + 1, thr: thr,
      spinning: true, blur: [true, true, true, true, true], hit: [false, false, false, false, false],
      msg: 'The wheel turns.', win: 0
    });
    if (this.timers) this.timers.forEach(clearInterval);
    this.timers = this.strips.map(function (s, r) {
      return setInterval(function () {
        var pos = self.state.pos.slice(); pos[r] = Math.floor(Math.random() * s.length);
        self.setState({ pos: pos });
      }, 70);
    });
    this.strips.forEach(function (s, r) {
      setTimeout(function () {
        clearInterval(self.timers[r]);
        var pos = self.state.pos.slice(); pos[r] = stops[r];
        var blur = self.state.blur.slice(); blur[r] = false;
        self.setState({ pos: pos, blur: blur });
        if (r === 4) self.evaluate(stops);
      }, fast ? 300 + r * 200 : 1200 + r * 550);
    });
  };
  Component.prototype.evaluate = function (stops) {
    var self = this, C = this.CFG;
    var syms = stops.map(function (p, r) { return self.strips[r][p]; });
    var gods = syms.filter(function (s) { return s.t === 'god'; });
    var offs = syms.filter(function (s) { return s.t === 'off'; }).length;
    var its = syms.filter(function (s) { return s.t === 'item'; });
    var RN = { P: 'Physical', L: 'Life', S: 'Spirits' };
    var PL = { 'pilgrim-s-blade': "Pilgrim's Blades", 'votive-charm': 'Votive Charms', 'prayer-beads': 'Prayer Beads', 'war-banner': 'War Banners', 'censer-of-devotion': 'Censers of Devotion', 'relic-shard': 'Relic Shards' };
    var NW = { 3: 'Three', 4: 'Four', 5: 'Five' };
    var mult = 0, msgs = [], god = false, hit = [false, false, false, false, false];
    var realmCount = { P: 0, L: 0, S: 0 };
    gods.forEach(function (g) { realmCount[g.realm]++; });
    var topRealm = ['P', 'L', 'S'].reduce(function (a, k) { return realmCount[k] > realmCount[a] ? k : a; }, 'P');
    var itemCount = {};
    its.forEach(function (i) { itemCount[i.id] = (itemCount[i.id] || 0) + 1; });
    var topItem = Object.keys(itemCount).reduce(function (a, k) { return itemCount[k] > (itemCount[a] || 0) ? k : a; }, null);
    if (realmCount[topRealm] >= 3) {
      var c = realmCount[topRealm];
      mult = C.payRealm[c]; god = true;
      hit = syms.map(function (s) { return s.t === 'god' && s.realm === topRealm; });
      msgs.push(NW[c] + ' thrones of the ' + RN[topRealm] + ' realm. The gods call for their flock.');
    } else if (gods.length >= 3 && realmCount.P > 0 && realmCount.L > 0 && realmCount.S > 0) {
      mult = C.payConf; god = true;
      hit = syms.map(function (s) { return s.t === 'god'; });
      msgs.push('The Confluence — every realm enthroned at once.');
    } else if (topItem && itemCount[topItem] >= 3) {
      var ci = itemCount[topItem];
      mult = C.payItem[ci];
      hit = syms.map(function (s) { return s.t === 'item' && s.id === topItem; });
      msgs.push(NW[ci] + ' ' + PL[topItem] + ' laid on the altar.');
    } else if (offs >= 3) {
      mult = C.payOff[offs];
      hit = syms.map(function (s) { return s.t === 'off'; });
      msgs.push(NW[offs] + ' offerings, gladly received.');
    } else if (its.length >= 3) {
      mult = C.payMixed3;
      hit = syms.map(function (s) { return s.t === 'item'; });
      msgs.push('A pilgrim’s bundle of wares.');
    } else if (realmCount[topRealm] === 2) {
      mult = C.payGodPair;
      hit = syms.map(function (s) { return s.t === 'god' && s.realm === topRealm; });
      msgs.push('Two gods of the ' + RN[topRealm] + ' realm regard you.');
    } else if (offs === 2) {
      mult = C.payOffPair;
      hit = syms.map(function (s) { return s.t === 'off'; });
      msgs.push('A modest pair of offerings.');
    } else if (topItem && itemCount[topItem] === 2) {
      mult = C.payItemPair;
      hit = syms.map(function (s) { return s.t === 'item' && s.id === topItem; });
      msgs.push('A matched pair of ' + PL[topItem] + '.');
    }
    // Meta: chart places, gather mortals
    var charted = this.state.charted.slice(), placeM = this.state.placeM.slice();
    syms.forEach(function (s) {
      if (s.t === 'place' && !charted[s.pIdx]) { charted[s.pIdx] = true; msgs.push(self.PLACES[s.pIdx].name + ' is charted.'); }
    });
    var chIdx = [0, 1, 2].filter(function (i) { return charted[i]; });
    var worReels = syms.map(function (s, r) { return s.t === 'wor' ? r : -1; }).filter(function (r) { return r >= 0; });
    var lead = Math.max(1, Math.round(C.mortalBase * this.state.bet / C.stakeRef));
    var flights = [];
    if (chIdx.length && worReels.length) {
      var godRealms = gods.map(function (g) { return g.realm; });
      var parts = [0, 0, 0];
      worReels.forEach(function () {
        var shares = chIdx.map(function (i) {
          return 1 + godRealms.filter(function (rl) { return rl === self.PLACES[i].realm; }).length;
        });
        var total = shares.reduce(function (a, b) { return a + b; }, 0);
        var given = 0;
        chIdx.forEach(function (i, k) { var amt = Math.floor(lead * shares[k] / total); parts[i] += amt; given += amt; });
        while (given < lead) { parts[chIdx[Math.floor(Math.random() * chIdx.length)]]++; given++; }
      });
      [0, 1, 2].forEach(function (i) { placeM[i] += parts[i]; });
      worReels.forEach(function (r) { chIdx.forEach(function (i) { if (parts[i] > 0) flights.push({ r: r, p: i }); }); });
    }
    // Boons: each god enthroned draws a share of a flock to their realm's charted place.
    var RIDX = { P: 0, L: 1, S: 2 };
    var boonBits = [], boonsFx = [];
    syms.forEach(function (s) {
      if (s.t !== 'god') return;
      var pi = RIDX[s.realm];
      if (!charted[pi]) return;
      var amt = Math.max(1, Math.round(C.boons[Math.floor(Math.random() * C.boons.length)] * lead));
      placeM[pi] += amt;
      boonsFx.push({ p: pi, god: s.id });
      boonBits.push(s.id.charAt(0).toUpperCase() + s.id.slice(1) + '’s boon draws ' + amt + ' faithful to ' + self.PLACES[pi].name + '.');
    });
    if (boonBits.length) msgs.push(boonBits.join(' '));
    if (flights.length) setTimeout(function () { self.spawnFlyers(flights); }, 150);
    if (boonsFx.length) setTimeout(function () { self.spawnBoons(boonsFx); }, 300);
    var thrIdx = [0, 1, 2].filter(function (i) { return charted[i] && placeM[i] >= self.state.thr[i]; })[0];
    var overflow = thrIdx !== undefined;
    if (overflow && !god) msgs.push(this.PLACES[thrIdx].name + ' overflows with the faithful.');
    if (msgs.length === 0) msgs.push('The road is quiet.');
    var win = mult * this.state.bet;
    this.setState({
      spinning: false, hit: hit, charted: charted, placeM: placeM, msg: msgs.join(' '), win: win, lastWin: win,
      balance: this.balNow() + win, won: this.state.won + win
    });
    if (god || overflow) {
      var fanGods = syms.filter(function (s, r) { return s.t === 'god' && hit[r]; });
      setTimeout(function () { self.startFanfare(god ? fanGods : [], overflow && !god ? thrIdx : -1); }, 900);
    }
  };
  Component.prototype.setFlyerPhase = function (k, ph) {
    this.setState({ flyers: (this.state.flyers || []).map(function (x) { return x.k === k ? Object.assign({}, x, { ph: ph }) : x; }) });
  };
  Component.prototype.pulsePlace = function (i, on) {
    var p = (this.state.placePulse || [false, false, false]).slice();
    p[i] = on;
    this.setState({ placePulse: p });
  };
  Component.prototype.spawnFlyers = function (pairs) {
    var self = this;
    if (!pairs.length) return;
    var flyers = [];
    pairs.forEach(function (pr, i) {
      var r = pr.r, p = pr.p;
      var reelEl = document.querySelector('[data-reel="' + r + '"]');
      var plEl = document.querySelector('[data-place="' + p + '"]');
      if (!reelEl || !plEl) return;
      var a = reelEl.getBoundingClientRect(), b = plEl.getBoundingClientRect();
      flyers.push({
        k: Date.now() + '-' + r + '-' + p + '-' + i,
        x: a.left + a.width / 2 - 33, y: a.top + a.height / 2 - 33,
        dx: (b.left + b.width / 2 - 33) - (a.left + a.width / 2 - 33),
        dy: (b.top + b.height * 0.72 - 33) - (a.top + a.height / 2 - 33),
        vh15: Math.round(window.innerHeight * 0.15),
        ph: 'in', dest: p, delay: i * 220
      });
    });
    if (!flyers.length) return;
    this.setState({ flyers: (this.state.flyers || []).concat(flyers) });
    var maxDelay = 0;
    flyers.forEach(function (f) {
      if (f.delay > maxDelay) maxDelay = f.delay;
      setTimeout(function () { self.setFlyerPhase(f.k, 'pop'); }, 40 + f.delay);
      setTimeout(function () { self.setFlyerPhase(f.k, 'dip'); }, 500 + f.delay);
      setTimeout(function () { self.setFlyerPhase(f.k, 'fly'); }, 1080 + f.delay);
      setTimeout(function () { self.setFlyerPhase(f.k, 'done'); self.pulsePlace(f.dest, true); }, 2350 + f.delay);
      setTimeout(function () { self.pulsePlace(f.dest, false); }, 3050 + f.delay);
    });
    // Remove all flyers in one batch AFTER the last lands — removing them one
    // by one shifts the list and makes survivors inherit siblings' transforms.
    setTimeout(function () { self.setState({ flyers: [] }); }, 2800 + maxDelay);
  };
  // God boon effects — each god strikes their realm's place with their own power.
  Component.prototype.BOONFX = {
    neptune: { c: '#2E7FA3', a: 'bfxSweep' }, raiden: { c: '#D9A62E', a: 'bfxStrike' }, vulcan: { c: '#B4552D', a: 'bfxRise' },
    helios: { c: '#D9A62E', a: 'bfxBurst' }, skadi: { c: '#7FB6C9', a: 'bfxDrift' },
    gaia: { c: '#5A7D4C', a: 'bfxRise' }, demeter: { c: '#A98B2D', a: 'bfxRise' }, pan: { c: '#6B8F5A', a: 'bfxSweep' },
    artemis: { c: '#90A8BB', a: 'bfxBurst' }, osiris: { c: '#4C8A63', a: 'bfxRise' },
    nike: { c: '#B8860B', a: 'bfxBurst' }, eris: { c: '#8A3033', a: 'bfxBurst' }, hestia: { c: '#C2703E', a: 'bfxRise' },
    anansi: { c: '#6B4E8E', a: 'bfxBurst' }, morpheus: { c: '#7A6B9E', a: 'bfxDrift' }
  };
  Component.prototype.boonGlyph = function (god, c) {
    var e = React.createElement, k = 0;
    var L = function (x1, y1, x2, y2, w, o) { return e('line', { key: 'l' + (k++), x1: x1, y1: y1, x2: x2, y2: y2, stroke: c, strokeWidth: w || 2.5, strokeLinecap: 'round', opacity: o == null ? 1 : o }); };
    var P = function (d, opt) { return e('path', Object.assign({ key: 'p' + (k++), d: d, stroke: c, strokeWidth: 3, fill: 'none', strokeLinecap: 'round', strokeLinejoin: 'round' }, opt)); };
    var C = function (cx, cy, r, opt) { return e('circle', Object.assign({ key: 'c' + (k++), cx: cx, cy: cy, r: r, stroke: c, strokeWidth: 2.5, fill: 'none' }, opt)); };
    var r, a, i;
    switch (god) {
      case 'neptune': return [P('M-12 66 Q4 52 20 66 T52 66 T84 66 T116 66'), P('M-12 80 Q8 70 28 80 T68 80 T108 80', { strokeWidth: 2, opacity: 0.6 })];
      case 'raiden': return [e('path', { key: 'r0', d: 'M58 4 L38 48 L53 48 L40 92 L70 42 L54 42 Z', fill: c })];
      case 'vulcan': return [e('path', { key: 'v0', d: 'M50 20 C63 37 69 52 60 67 C58 56 51 54 50 45 C42 56 37 63 43 74 C27 59 33 36 50 20 Z', fill: c }), C(36, 32, 2, { fill: c, stroke: 'none' }), C(66, 28, 1.6, { fill: c, stroke: 'none' })];
      case 'helios': { r = [C(50, 42, 10)]; for (i = 0; i < 8; i++) { a = i * Math.PI / 4; r.push(L(50 + Math.cos(a) * 15, 42 + Math.sin(a) * 15, 50 + Math.cos(a) * 24, 42 + Math.sin(a) * 24)); } return r; }
      case 'skadi': { var fl = function (cx, cy, s, o) { return [0, 60, 120].map(function (dg, n) { return e('line', { key: 'sk' + cx + n, x1: cx, y1: cy - s, x2: cx, y2: cy + s, stroke: c, strokeWidth: 2, strokeLinecap: 'round', opacity: o, transform: 'rotate(' + dg + ' ' + cx + ' ' + cy + ')' }); }); }; return [].concat(fl(32, 38, 8, 1), fl(62, 26, 6, 0.8), fl(72, 58, 7, 0.9)); }
      case 'gaia': return [P('M50 86 Q50 62 50 44', { strokeWidth: 2.5 }), e('path', { key: 'g1', d: 'M50 64 Q35 58 31 44 Q47 47 50 60 Z', fill: c, opacity: 0.9 }), e('path', { key: 'g2', d: 'M50 54 Q65 48 69 34 Q53 37 50 50 Z', fill: c, opacity: 0.9 })];
      case 'demeter': { var st = function (x, ln) { return [P('M' + x + ' 84 Q' + (x + ln) + ' 60 ' + (x + ln * 2) + ' 34', { strokeWidth: 2 })].concat([0.35, 0.55, 0.75].map(function (t) { return C(x + ln * 2 * t, 84 - t * 50, 2, { fill: c, stroke: 'none' }); })); }; return [].concat(st(36, 2), st(50, 0), st(64, -2)); }
      case 'pan': return [P('M-8 36 Q28 26 52 36 Q68 42 80 32', { strokeWidth: 2.5 }), P('M-8 52 Q24 44 50 52 Q64 57 76 50', { strokeWidth: 2, opacity: 0.7 }), P('M-8 66 Q20 60 44 66', { strokeWidth: 1.8, opacity: 0.5 })];
      case 'artemis': return [e('path', { key: 'a0', d: 'M60 20 A24 24 0 1 0 60 72 A19 19 0 1 1 60 20 Z', fill: c, opacity: 0.9 }), L(64, 60, 86, 34, 2, 0.8)];
      case 'osiris': return [C(50, 32, 10), L(50, 42, 50, 82, 3), L(35, 54, 65, 54, 3)];
      case 'nike': return [e('path', { key: 'n0', d: 'M50 74 Q28 66 16 42 Q36 52 50 56 Z', fill: c, opacity: 0.85 }), e('path', { key: 'n1', d: 'M50 74 Q72 66 84 42 Q64 52 50 56 Z', fill: c, opacity: 0.85 })];
      case 'eris': return [P('M50 46 L62 34 L60 24', { strokeWidth: 2.5 }), P('M50 46 L64 52 L76 48', { strokeWidth: 2.5 }), P('M50 46 L52 64 L44 74', { strokeWidth: 2.5 }), P('M50 46 L36 54 L24 50', { strokeWidth: 2.5 }), P('M50 46 L40 34 L42 22', { strokeWidth: 2.5 }), C(50, 46, 3, { fill: c, stroke: 'none' })];
      case 'hestia': return [P('M32 80 Q32 58 50 58 Q68 58 68 80'), e('path', { key: 'h0', d: 'M50 62 C55 68 57 72 53 78 C52 74 49 73 49 70 C46 74 45 76 47 79 C41 74 44 66 50 62 Z', fill: c })];
      case 'anansi': { r = [C(50, 46, 10, { opacity: 0.8 }), C(50, 46, 19, { opacity: 0.5 })]; for (i = 0; i < 6; i++) { a = i * Math.PI / 3; r.push(L(50, 46, 50 + Math.cos(a) * 24, 46 + Math.sin(a) * 24, 1.8, 0.9)); } return r; }
      case 'morpheus': return [C(38, 52, 12, { fill: c, stroke: 'none', opacity: 0.35 }), C(58, 42, 15, { fill: c, stroke: 'none', opacity: 0.3 }), C(66, 60, 9, { fill: c, stroke: 'none', opacity: 0.4 })];
      default: return [C(50, 46, 12)];
    }
  };
  Component.prototype.renderBoonFx = function () {
    var self = this, e = React.createElement, fxs = this.state.boonFx || [];
    return e('div', { style: { position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 45 } },
      fxs.map(function (f) {
        var g = self.BOONFX[f.god] || { c: '#B8860B', a: 'bfxBurst' };
        var size = Math.min(f.w, f.h) * 1.15;
        return e('div', { key: f.k, style: { position: 'absolute', left: f.x + 'px', top: f.y + 'px', width: f.w + 'px', height: f.h + 'px', display: 'flex', alignItems: 'flex-end', justifyContent: 'center', overflow: 'hidden' } },
          e('div', { style: { position: 'absolute', left: '10%', right: '10%', bottom: '4%', height: '18%', borderRadius: '50%', background: 'radial-gradient(ellipse at center, ' + g.c + 'AA 0%, transparent 70%)', animation: 'bfxGround 2200ms cubic-bezier(0.16,1,0.3,1) ' + f.delay + 'ms both' } }),
          e('svg', {
            viewBox: '0 0 100 100', width: size, height: size,
            style: { overflow: 'visible', filter: 'drop-shadow(0 0 6px #FFF8E7) drop-shadow(0 0 16px ' + g.c + ') drop-shadow(0 0 30px ' + g.c + ')', animation: g.a + ' 2200ms cubic-bezier(0.16,1,0.3,1) ' + f.delay + 'ms both' }
          }, self.boonGlyph(f.god, g.c)));
      }));
  };
  Component.prototype.spawnBoons = function (list) {
    var self = this, fx = [];
    list.forEach(function (b, i) {
      var plEl = document.querySelector('[data-place="' + b.p + '"]');
      if (!plEl) return;
      var r = plEl.getBoundingClientRect();
      fx.push({ k: 'bfx' + Date.now() + '-' + i, god: b.god, p: b.p, x: r.left, y: r.top, w: r.width, h: r.height, delay: i * 450 });
    });
    if (!fx.length) return;
    this.setState({ boonFx: (this.state.boonFx || []).concat(fx) });
    var maxD = 0;
    fx.forEach(function (f) {
      if (f.delay > maxD) maxD = f.delay;
      setTimeout(function () { self.pulsePlace(f.p, true); }, 1100 + f.delay);
      setTimeout(function () { self.pulsePlace(f.p, false); }, 2200 + f.delay);
    });
    setTimeout(function () { self.setState({ boonFx: [] }); }, 2500 + maxD);
  };
  Component.prototype.startFanfare = function (fanGods, overflowIdx) {
    var self = this;
    var RC = { P: '#15708C', L: '#5A7D4C', S: '#8A3033' }, RN = { P: 'Physical', L: 'Life', S: 'Spirits' };
    var mortals = this.state.placeM[0] + this.state.placeM[1] + this.state.placeM[2];
    var focus, title, sub;
    if (fanGods.length) {
      focus = fanGods.map(function (g) { return { img: g.img, ring: RC[g.realm] }; });
      var realms = fanGods.map(function (g) { return g.realm; }).filter(function (v, i, a) { return a.indexOf(v) === i; });
      title = realms.length > 1 ? 'The Confluence' : 'The ' + RN[realms[0]] + ' realm enthroned';
      sub = (mortals > 0 ? mortals.toLocaleString() + ' mortals' : 'The mortals') + ' line up before the thrones.';
    } else {
      var pl = this.PLACES[overflowIdx];
      focus = [{ img: pl.img, ring: 'var(--discover-gold)' }];
      title = pl.name + ' overflows';
      sub = 'The faithful spill past its gates — the rite must be sung.';
    }
    this.setState({ fanfare: { focus: focus, title: title, sub: sub, overflowIdx: overflowIdx } });
    setTimeout(function () {
      if (!self.state.fanfare) return;
      self.setState({ fanfare: null });
      self.startBonus(overflowIdx);
    }, 5200);
  };
  Component.prototype.startBonus = function (overflowIdx) {
    var mortals = this.state.placeM[0] + this.state.placeM[1] + this.state.placeM[2];
    var title = overflowIdx >= 0 ? this.PLACES[overflowIdx].name + ' overflows' : 'The flock gathers';
    this.setState({ bonus: { pos: [0, 0, 0, 0, 0], blur: [false, false, false, false, false], spinning: false, mortals: mortals, title: title, log: [], done: false, spinN: 0 } });
  };
  Component.prototype.bonusSpin = function () {
    var self = this, b = this.state.bonus;
    if (!b || b.spinning || b.done) return;
    var stops = this.bStrips.map(function (s) { return Math.floor(Math.random() * s.length); });
    var fast = this.props.fastSpins;
    this.setState({ bonus: Object.assign({}, b, { spinning: true, blur: [true, true, true, true, true] }) });
    if (this.bTimers) this.bTimers.forEach(clearInterval);
    this.bTimers = this.bStrips.map(function (s, r) {
      return setInterval(function () {
        var bb = self.state.bonus; if (!bb) return;
        var pos = bb.pos.slice(); pos[r] = Math.floor(Math.random() * s.length);
        self.setState({ bonus: Object.assign({}, bb, { pos: pos }) });
      }, 70);
    });
    this.bStrips.forEach(function (s, r) {
      setTimeout(function () {
        clearInterval(self.bTimers[r]);
        var bb = self.state.bonus; if (!bb) return;
        var pos = bb.pos.slice(); pos[r] = stops[r];
        var blur = bb.blur.slice(); blur[r] = false;
        self.setState({ bonus: Object.assign({}, bb, { pos: pos, blur: blur }) });
        if (r === 4) self.evalBonus(stops);
      }, fast ? 250 + r * 180 : 800 + r * 450);
    });
  };
  Component.prototype.evalBonus = function (stops) {
    var self = this, C = this.CFG, b = this.state.bonus;
    var syms = stops.map(function (p, r) { return self.bStrips[r][p]; });
    var worN = syms.filter(function (s) { return s.t === 'wor'; }).reduce(function (a, s) { return a + s.n; }, 0);
    var spinN = b.spinN + 1;
    if (worN === 0 && b.spinN >= C.minRiteSpins) {
      this.setState({ bonus: Object.assign({}, b, { spinning: false, done: true, spinN: spinN, log: [{ text: 'Spin ' + spinN + ' — no new voice joins. The hymn fades.' }].concat(b.log) }) });
      return;
    }
    var add = 0;
    syms.forEach(function (s) {
      if (s.t === 'wor') add += s.n * self.rint(C.bonusWorGain[0], C.bonusWorGain[1]);
      else if (s.t === 'item') add += C.bonusItemM;
      else if (s.t === 'place') add += C.bonusPlaceM;
    });
    add = Math.max(1, Math.round(add * this.state.bet / C.stakeRef));
    var mortals = b.mortals + add;
    this.setState({
      bonus: Object.assign({}, b, {
        spinning: false, mortals: mortals, spinN: spinN,
        log: [{ text: 'Spin ' + spinN + ' — ' + add + ' mortals pour in (' + mortals.toLocaleString() + ' gathered)' + (worN === 0 ? ' · the hymn holds' : '') }].concat(b.log)
      })
    });
  };
  Component.prototype.collectBonus = function () {
    var b = this.state.bonus; if (!b) return;
    var pay = b.mortals * this.CFG.payPerMortal;
    this.setState({
      bonus: null, balance: this.balNow() + pay, won: this.state.won + pay,
      charted: [false, false, false], placeM: [0, 0, 0], thr: this.rollThr(),
      msg: pay > 0 ? b.mortals.toLocaleString() + ' mortals offer their worship. ' + this.fmt(pay) + ' carried home. The map is wiped clean.' : 'The rite passes unheard.',
      win: 0, lastWin: pay > 0 ? pay : this.state.lastWin
    });
  };
  Component.prototype.componentDidMount = function () {
    var self = this;
    this.rc = setInterval(function () {
      var mins = self.props.realityCheckMinutes != null ? self.props.realityCheckMinutes : 60;
      var elapsed = (Date.now() - self.state.sessionStart) / 60000;
      if (elapsed - self.state.rcShown >= mins && !self.state.spinning) self.setState({ rcShown: elapsed, modal: 'reality' });
    }, 30000);
  };
  Component.prototype.componentWillUnmount = function () {
    if (this.rc) clearInterval(this.rc);
    if (this.timers) this.timers.forEach(clearInterval);
    if (this.bTimers) this.bTimers.forEach(clearInterval);
  };
  Component.prototype.renderVals = function () {
    var self = this;
    if (!this.strips) this.buildData();
    var st = this.state, bal = this.balNow();
    var RC = { P: '#15708C', L: '#5A7D4C', S: '#8A3033' };
    var reels = this.strips.map(function (s, r) {
      var n = s.length, p = ((st.pos[r] % n) + n) % n;
      var at = function (i) { return s[((i % n) + n) % n]; };
      var mid = at(p);
      return {
        idx: r,
        topImg: at(p - 1).img || '', midImg: mid.img || '', botImg: at(p + 1).img || '',
        midQuiet: !mid.img,
        blurCss: st.blur[r] ? 'blur(2px) saturate(0.85)' : 'none',
        outline: st.hit[r] ? '3px solid var(--discover-gold)' : '3px solid transparent',
        glow: st.hit[r] ? '0 0 22px rgba(184,134,11,0.45)' : 'none',
        bar: mid.t === 'god' ? RC[mid.realm] : 'var(--border-medium)'
      };
    });
    var flyers = (st.flyers || []).map(function (f) {
      if (f.ph === 'in') return { k: f.k, x: f.x + 'px', y: f.y + 'px', tr: 'translate(0,0) scale(0.25) rotate(-18deg)', op: '0', glow: 'drop-shadow(0 0 6px rgba(184,134,11,0.0))', trans: 'none' };
      if (f.ph === 'pop') return { k: f.k, x: f.x + 'px', y: f.y + 'px', tr: 'translate(0,-10px) scale(1.5) rotate(0deg)', op: '1', glow: 'drop-shadow(0 0 18px rgba(184,134,11,0.85))', trans: 'transform 420ms cubic-bezier(0.16,1,0.3,1), opacity 300ms, filter 420ms' };
      if (f.ph === 'dip') return { k: f.k, x: f.x + 'px', y: f.y + 'px', tr: 'translate(' + Math.round(f.dx * 0.25) + 'px,' + f.vh15 + 'px) scale(1.35) rotate(-8deg)', op: '1', glow: 'drop-shadow(0 0 14px rgba(184,134,11,0.7))', trans: 'transform 600ms cubic-bezier(0.5,0,0.75,0.5)' };
      if (f.ph === 'done') return { k: f.k, x: f.x + 'px', y: f.y + 'px', tr: 'translate(' + f.dx + 'px,' + f.dy + 'px) scale(0.5) rotate(8deg)', op: '0', glow: 'none', trans: 'opacity 300ms' };
      return { k: f.k, x: f.x + 'px', y: f.y + 'px', tr: 'translate(' + f.dx + 'px,' + f.dy + 'px) scale(0.5) rotate(8deg)', op: '0.9', glow: 'drop-shadow(0 0 10px rgba(184,134,11,0.6))', trans: 'transform 1300ms cubic-bezier(0.16,1,0.3,1), opacity 1300ms, filter 1300ms' };
    });
    var pulse = st.placePulse || [false, false, false];
    // scatter slots within each panorama third (percent coords, ground band, filled bottom-up)
    var SLOTS = [
      { l: 40, b: 5 }, { l: 58, b: 4 }, { l: 24, b: 8 }, { l: 72, b: 9 },
      { l: 48, b: 12 }, { l: 32, b: 16 }, { l: 64, b: 17 }, { l: 54, b: 22 },
      { l: 38, b: 26 }, { l: 68, b: 27 }, { l: 48, b: 32 }, { l: 28, b: 34 },
      { l: 60, b: 38 }, { l: 44, b: 42 }
    ];
    var placesTrack = this.PLACES.map(function (pl, i) {
      return {
        idx: i, name: pl.name,
        left: (i * 33.333) + '%', imgLeft: '-' + (i * 100) + '%',
        revealOp: st.charted[i] ? '1' : '0',
        pulseOp: pulse[i] ? '1' : '0',
        nameColor: st.charted[i] ? '#FFF8E7' : 'rgba(247,245,242,0.55)',
        crowd: SLOTS.slice(0, Math.min(14, Math.ceil(st.placeM[i] / 20))).map(function (s, k) { return { k: k, l: s.l + '%', b: s.b + '%' }; })
      };
    });
    var b = st.bonus;
    var bonusReels = (b ? this.bStrips : []).map(function (s, r) {
      var n = s.length, sym = s[((b.pos[r] % n) + n) % n];
      return { img: sym.img || '', quiet: !sym.img, isWor: sym.t === 'wor' && !b.blur[r], worN: sym.n || 0, blurCss: b.blur[r] ? 'blur(2px)' : 'none' };
    });
    return {
      balance: this.fmt(bal), betFmt: this.fmt(st.bet), lastWinFmt: this.fmt(st.lastWin),
      mortalsTotal: (st.placeM[0] + st.placeM[1] + st.placeM[2]).toLocaleString(),
      msg: st.msg, hasWin: st.win > 0, winText: '+' + this.fmt(st.win) + ' worship',
      reels: reels, placesTrack: placesTrack, flyers: flyers, allImgs: this.allImgs, boonFxLayer: this.renderBoonFx(),
      spin: function () { self.spin(); },
      spinLabel: st.spinning ? 'The wheel turns' : 'Spin',
      spinDisabled: st.spinning || !!st.bonus || !!st.fanfare || bal < st.bet,
      hasFanfare: !!st.fanfare,
      fanfareTitle: st.fanfare ? st.fanfare.title : '',
      fanfareSub: st.fanfare ? st.fanfare.sub : '',
      fanfareGods: st.fanfare ? st.fanfare.focus.map(function (g, i) { return { img: g.img, ring: g.ring, delay: 300 + i * 240, bobDelay: 1100 + i * 240 }; }) : [],
      fanfareWor: st.fanfare ? Array.from({ length: 16 }, function (_, i) { return { size: (i % 3 === 0 ? 46 : 38) + 'px', delay: 1200 + i * 140, bobDelay: 1850 + i * 140 }; }) : [],
      noCoins: bal < st.bet && !st.spinning,
      betUp: function () { self.stepBet(1); }, betDown: function () { self.stepBet(-1); },
      addCoins: function () { self.addCoins(); },
      openPaytable: function () { self.setState({ modal: 'pay' }); },
      openHelp: function () { self.setState({ modal: 'help' }); },
      closeModal: function () { self.setState({ modal: null }); },
      showPay: st.modal === 'pay', showHelp: st.modal === 'help', showReality: st.modal === 'reality',
      sessionMins: String(Math.floor((Date.now() - st.sessionStart) / 60000)),
      sessionSpins: String(st.spins), sessionStaked: this.fmt(st.staked), sessionEarned: this.fmt(st.won),
      hasBonus: !!b,
      bonusReels: bonusReels,
      bonusTitle: b ? b.title : '',
      bonusMortals: b ? b.mortals.toLocaleString() : '0',
      bonusPayout: b ? this.fmt(b.mortals * this.CFG.payPerMortal) : '0',
      bonusActive: !!b && !b.done, bonusDone: !!b && b.done,
      bonusSpinning: !!b && b.spinning,
      bonusSpin: function () { self.bonusSpin(); },
      collectBonus: function () { self.collectBonus(); },
      bonusLog: b ? b.log : []
    };
  };

  /* =========================================================
     Template — the canvas markup, ported to createElement
     ========================================================= */
  var MONO = { fontFamily: 'var(--font-mono)' };
  var PROSE = { fontFamily: 'var(--font-prose)' };
  var EYEBROW = { fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' };
  var STAT_LABEL = { fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' };
  var LINKBTN = { border: 'none', background: 'none', color: 'var(--place-base)', fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 500, cursor: 'pointer', textDecoration: 'underline', textUnderlineOffset: '2px' };
  var MODAL_WRAP = { position: 'fixed', inset: 0, background: 'rgba(26,23,20,0.5)', zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 };
  var MODAL_CARD = { maxHeight: '88vh', overflowY: 'auto', background: 'var(--surface-raised)', border: '1px solid var(--border-subtle)', borderRadius: 20, boxShadow: '0 12px 40px rgba(26,23,20,0.35)', padding: '28px 32px', boxSizing: 'border-box' };

  function payRow(label, value, i) {
    return [
      h('div', { key: 'l' + i }, label),
      h('div', { key: 'v' + i, style: Object.assign({}, MONO, { textAlign: 'right' }) }, value)
    ];
  }

  function view(V) {
    return h('div', { style: { minHeight: '100vh', background: 'var(--surface-page)', color: 'var(--text-primary)', fontFamily: 'var(--font-ui)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 24px 56px' } },

      /* ---- header ---- */
      h('div', { style: { textAlign: 'center', marginBottom: 22 } },
        h('div', { style: Object.assign({}, EYEBROW, { color: 'var(--text-tertiary)' }) }, 'Seeklore · Game mockup'),
        h('h1', { style: Object.assign({}, PROSE, { fontSize: 42, fontWeight: 700, letterSpacing: '-0.02em', margin: '10px 0 8px' }) }, 'The Votive Wheel'),
        h('div', { style: Object.assign({}, PROSE, { fontStyle: 'italic', fontSize: 17, color: 'var(--text-secondary)' }) }, 'Chart the sacred places, gather mortals to them, and seat the gods to call the flock home.')),

      /* ---- machine ---- */
      h('div', { style: { background: 'var(--surface-raised)', border: '1px solid var(--border-subtle)', borderRadius: 12, boxShadow: '0 8px 30px rgba(26,23,20,0.10)', padding: '26px 34px', maxWidth: 960, width: '100%', boxSizing: 'border-box' } },

        /* panorama */
        h('div', { style: { position: 'relative', width: '100%', aspectRatio: '1536/672', marginBottom: 24, borderRadius: 12, overflow: 'hidden', border: '1px solid var(--border-medium)', background: 'var(--surface-sunken)' } },
          h('img', { src: 'symbols-web/panorama-pilgrim-coast.jpg', alt: '', style: { position: 'absolute', inset: 0, width: '100%', height: '100%', filter: 'grayscale(1)', opacity: 0.4 } }),
          V.placesTrack.map(function (pl) {
            return h('div', { key: 'pl' + pl.idx, 'data-place': pl.idx, style: { position: 'absolute', top: 0, bottom: 0, left: pl.left, width: '33.334%' } },
              h('div', { style: { position: 'absolute', inset: 0, overflow: 'hidden', opacity: pl.revealOp, transition: 'opacity 900ms' } },
                h('img', { src: 'symbols-web/panorama-pilgrim-coast.jpg', alt: '', style: { position: 'absolute', top: 0, left: pl.imgLeft, width: '300%', height: '100%' } })),
              h('div', { style: { position: 'absolute', inset: 0, boxShadow: 'inset 0 0 0 2px var(--discover-gold), inset 0 0 34px rgba(184,134,11,0.55)', opacity: pl.pulseOp, transition: 'opacity 500ms', pointerEvents: 'none' } }),
              pl.crowd.map(function (cw) {
                return h('img', { key: 'cw' + cw.k, src: 'symbols-web/worshippers-1.png', alt: '', style: { position: 'absolute', width: 28, height: 28, left: cw.l, bottom: cw.b, transform: 'translateX(-50%)', filter: 'drop-shadow(0 1px 3px rgba(26,23,20,0.5))' } });
              }),
              h('div', { style: Object.assign({}, PROSE, { position: 'absolute', left: 0, right: 0, bottom: 6, textAlign: 'center', fontSize: 12, fontWeight: 600, color: pl.nameColor, textShadow: '0 1px 4px rgba(26,23,20,0.65)', transition: 'color 700ms' }) }, pl.name));
          })),

        /* reels */
        h('div', { style: { position: 'relative', display: 'flex', justifyContent: 'center', gap: 14 } },
          h('div', { style: { position: 'absolute', left: -10, top: '50%', transform: 'translateY(-50%)', color: 'var(--discover-gold)', fontSize: 18 } }, '▸'),
          h('div', { style: { position: 'absolute', right: -10, top: '50%', transform: 'translateY(-50%)', color: 'var(--discover-gold)', fontSize: 18 } }, '◂'),
          V.reels.map(function (reel) {
            return h('div', { key: 'r' + reel.idx, 'data-reel': reel.idx, style: { width: 148, borderRadius: 12, border: '1px solid var(--border-medium)', background: 'var(--surface-sunken)', overflow: 'hidden', filter: reel.blurCss, transition: 'filter 120ms' } },
              h('div', { style: { height: 44, overflow: 'hidden', opacity: 0.32 } },
                reel.topImg ? h('img', { src: reel.topImg, alt: '', style: { width: '100%', display: 'block', marginTop: -100 } }) : null),
              h('div', { style: { padding: 6, background: 'var(--surface-raised)', borderTop: '1px solid var(--border-subtle)', borderBottom: '1px solid var(--border-subtle)' } },
                reel.midImg ? h('img', { src: reel.midImg, alt: '', style: { width: '100%', display: 'block', borderRadius: 6, outline: reel.outline, outlineOffset: -1, boxShadow: reel.glow } }) : null,
                reel.midQuiet ? h('div', { style: { aspectRatio: '1/1', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, color: 'var(--text-tertiary)' } },
                  h('div', { style: { fontSize: 18, letterSpacing: '0.2em' } }, '···'),
                  h('div', { style: Object.assign({}, PROSE, { fontStyle: 'italic', fontSize: 12 }) }, 'The quiet road')) : null,
                h('div', { style: { height: 4, borderRadius: 2, marginTop: 6, background: reel.bar } })),
              h('div', { style: { height: 44, overflow: 'hidden', opacity: 0.32 } },
                reel.botImg ? h('img', { src: reel.botImg, alt: '', style: { width: '100%', display: 'block' } }) : null));
          })),

        /* message */
        h('div', { style: { minHeight: 56, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2, margin: '18px 0 6px', textAlign: 'center' } },
          h('div', { style: Object.assign({}, PROSE, { fontStyle: 'italic', fontSize: 18, color: 'var(--text-secondary)' }) }, V.msg),
          V.hasWin ? h('div', { style: Object.assign({}, PROSE, { fontSize: 22, fontWeight: 600, color: 'var(--discover-gold)' }) }, V.winText) : null),

        /* controls */
        h('div', { style: { display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 24, borderTop: '1px solid var(--border-subtle)', paddingTop: 20 } },
          h('div', { style: { display: 'flex', gap: 32 } },
            h('div', null,
              h('div', { style: Object.assign({}, STAT_LABEL, { color: 'var(--discover-gold)' }) }, 'Worship'),
              h('div', { style: Object.assign({}, MONO, { fontSize: 22, marginTop: 2 }) }, V.balance)),
            h('div', null,
              h('div', { style: Object.assign({}, STAT_LABEL, { color: 'var(--text-tertiary)' }) }, 'Stake'),
              h('div', { style: { display: 'flex', alignItems: 'center', gap: 10, marginTop: 2 } },
                h('button', { aria: 'Lower stake', 'aria-label': 'Lower stake', onClick: V.betDown, className: 'step-btn', style: { width: 28, height: 28, borderRadius: 8, border: '1px solid var(--border-medium)', background: 'var(--surface-page)', color: 'var(--text-primary)', fontSize: 15, cursor: 'pointer' } }, '−'),
                h('span', { style: Object.assign({}, MONO, { fontSize: 22, minWidth: 74, textAlign: 'center' }) }, V.betFmt),
                h('button', { 'aria-label': 'Raise stake', onClick: V.betUp, className: 'step-btn', style: { width: 28, height: 28, borderRadius: 8, border: '1px solid var(--border-medium)', background: 'var(--surface-page)', color: 'var(--text-primary)', fontSize: 15, cursor: 'pointer' } }, '+')))),
          h(Button, { variant: 'primary', size: 'md', onClick: V.spin, disabled: V.spinDisabled }, V.spinLabel),
          h('div', { style: { display: 'flex', gap: 32, justifyContent: 'flex-end' } },
            h('div', { style: { textAlign: 'right' } },
              h('div', { style: Object.assign({}, STAT_LABEL, { color: 'var(--text-tertiary)' }) }, 'Mortals gathered'),
              h('div', { style: Object.assign({}, MONO, { fontSize: 22, marginTop: 2 }) }, V.mortalsTotal)),
            h('div', { style: { textAlign: 'right' } },
              h('div', { style: Object.assign({}, STAT_LABEL, { color: 'var(--text-tertiary)' }) }, 'Last win'),
              h('div', { style: Object.assign({}, MONO, { fontSize: 22, marginTop: 2 }) }, V.lastWinFmt)))),

        V.noCoins ? h('div', { style: { textAlign: 'center', marginTop: 14 } },
          h('button', { onClick: V.addCoins, style: Object.assign({}, LINKBTN, { fontWeight: 400 }) }, 'The purse is empty — add 2,000 worship (mock wallet)')) : null),

      /* ---- secondary links ---- */
      h('div', { style: { display: 'flex', gap: 20, marginTop: 18 } },
        h('button', { onClick: V.openPaytable, style: LINKBTN }, 'Paytable'),
        h('button', { onClick: V.openHelp, style: LINKBTN }, 'How it plays')),

      /* ---- standing disclosure ---- */
      h('div', { style: { maxWidth: 660, textAlign: 'center', marginTop: 22, fontSize: 11, lineHeight: 1.6, color: 'var(--text-tertiary)' } },
        'Design mockup — not a gambling product. Worship is the game’s currency: one worship equals one cent, shown in whole worship. Theoretical RTP ≈ 94% at a 100-worship stake (sim-validated; uncertified client-side RNG, visuals reflect the drawn result exactly). Single payline · minimum spin ~3.4s · no autoplay · a quiet word appears each hour of play.'),

      /* ---- Worshipper Rite ---- */
      V.hasBonus ? h('div', { style: { position: 'fixed', inset: 0, background: 'rgba(26,23,20,0.62)', zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 } },
        h('div', { style: { width: 'min(880px,94vw)', maxHeight: '92vh', overflowY: 'auto', background: 'var(--surface-raised)', border: '2px solid var(--discover-gold)', borderRadius: 20, boxShadow: '0 12px 40px rgba(26,23,20,0.35)', padding: '30px 34px', boxSizing: 'border-box' } },
          h('div', { style: { textAlign: 'center' } },
            h('div', { style: Object.assign({}, EYEBROW, { color: 'var(--discover-gold)' }) }, 'Worshipper Rite'),
            h('div', { style: Object.assign({}, PROSE, { fontSize: 30, fontWeight: 700, margin: '6px 0 4px' }) }, V.bonusTitle),
            h('div', { style: Object.assign({}, PROSE, { fontStyle: 'italic', fontSize: 15, color: 'var(--text-secondary)' }) }, 'Mortals pour in while the hymn holds — the first three rounds always hold. After that, a spin with no new voice ends the rite, and every mortal offers 5 worship.')),
          h('div', { style: { display: 'flex', justifyContent: 'center', gap: 44, margin: '20px 0 18px' } },
            h('div', { style: { textAlign: 'center' } },
              h('div', { style: Object.assign({}, STAT_LABEL, { color: 'var(--text-tertiary)' }) }, 'Mortals'),
              h('div', { style: Object.assign({}, MONO, { fontSize: 26 }) }, V.bonusMortals)),
            h('div', { style: { textAlign: 'center' } },
              h('div', { style: Object.assign({}, STAT_LABEL, { color: 'var(--discover-gold)' }) }, 'Worship at close'),
              h('div', { style: Object.assign({}, MONO, { fontSize: 26, color: 'var(--discover-gold)' }) }, V.bonusPayout))),
          h('div', { style: { display: 'flex', justifyContent: 'center', gap: 14 } },
            V.bonusReels.map(function (r, i) {
              return h('div', { key: 'br' + i, style: { position: 'relative', width: 128, borderRadius: 10, border: '1px solid var(--border-medium)', background: 'var(--surface-sunken)', overflow: 'hidden', filter: r.blurCss, transition: 'filter 120ms' } },
                r.img ? h('img', { src: r.img, alt: '', style: { width: '100%', display: 'block' } }) : null,
                r.quiet ? h('div', { style: { width: 128, height: 126, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, color: 'var(--text-tertiary)' } },
                  h('div', { style: { fontSize: 20, letterSpacing: '0.2em' } }, '···'),
                  h('div', { style: Object.assign({}, PROSE, { fontStyle: 'italic', fontSize: 12 }) }, 'The quiet road')) : null,
                r.isWor ? h('div', { style: { position: 'absolute', top: 6, right: 6, background: 'var(--discover-gold)', color: '#FFF8E7', fontSize: 12, fontWeight: 600, borderRadius: 8, padding: '2px 7px' } }, '×' + r.worN) : null);
            })),
          h('div', { style: { minHeight: 20, textAlign: 'center', marginTop: 16 } },
            V.bonusActive ? h(Button, { variant: 'primary', size: 'md', onClick: V.bonusSpin, disabled: V.bonusSpinning }, 'Sound the hymn') : null,
            V.bonusDone ? h(Button, { variant: 'primary', size: 'md', onClick: V.collectBonus }, 'Carry worship home') : null),
          h('div', { style: { maxHeight: 132, overflowY: 'auto', marginTop: 16, borderTop: '1px solid var(--border-subtle)', paddingTop: 10 } },
            V.bonusLog.map(function (entry, i) {
              return h('div', { key: 'lg' + i, style: { fontSize: 13, color: 'var(--text-secondary)', padding: '3px 0' } }, entry.text);
            })))) : null,

      /* ---- paytable ---- */
      V.showPay ? h('div', { style: MODAL_WRAP, onClick: V.closeModal },
        h('div', { style: Object.assign({ width: 'min(580px,94vw)' }, MODAL_CARD), onClick: function (e) { e.stopPropagation(); } },
          h('div', { style: Object.assign({}, EYEBROW, { color: 'var(--text-tertiary)' }) }, 'Paytable · Single centre line · pays × stake'),
          h('div', { style: { display: 'grid', gridTemplateColumns: '1fr auto', gap: '9px 16px', marginTop: 16, fontSize: 14 } },
            payRow([h('span', { key: 'a' }, 'Gods of one realm — five · four · three '), h('span', { key: 'b', style: { color: 'var(--discover-gold)' } }, '+ Rite')], '200× · 50× · 10×', 0),
            payRow([h('span', { key: 'a' }, '✦ The Confluence — all three realms enthroned '), h('span', { key: 'b', style: { color: 'var(--discover-gold)' } }, '+ Rite')], '6×', 1),
            payRow('Same item — five · four · three', '35× · 12× · 5×', 2),
            payRow('Offerings — five · four · three', '20× · 8× · 3×', 3),
            payRow('Any three items', '0.4×', 4),
            payRow('Two gods of one realm', '0.4×', 5),
            payRow('Two Offerings', '0.3×', 6),
            payRow('Two of the same item', '0.2×', 7)),
          h('div', { style: { marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border-subtle)', fontSize: 13, lineHeight: 1.7, color: 'var(--text-secondary)' } },
            h('div', { style: Object.assign({}, STAT_LABEL, { color: 'var(--text-tertiary)', marginBottom: 6 }) }, 'The mortal economy'),
            'A sacred place landing on the line charts it above the wheel. Each mortal on the line then leads 10 mortals, divided by shares among the charted places — every charted place holds one share, and each god on the line adds a share to the place of its realm. Each god enthroned also grants a boon in its own power — a quarter, half, three-quarters, or a full flock of ten, drawn straight to the charted place of its realm. The Worshipper Rite begins when three gods of one realm land, the Confluence lands, or any one place quietly overflows (a hidden count between 100 and 1,000). In the Rite, mortals ×2–4 pour in per worshipper head, +2 per item, +4 per place; the first three rounds always hold, and after that a spin with no new voice ends the rite — then every mortal offers 5 worship, and the map is wiped clean. The flock scales with your stake: at 200 worship each mortal on the line leads 20, at 25 it leads 3 — the Rite pours in at the same rate.'),
          h('div', { style: { marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', fontSize: 12, lineHeight: 1.6, color: 'var(--text-tertiary)' } },
            'Each reel carries 18 cards: three gods (one per realm), six items, two Offerings, two places, two mortals, and three quiet roads. Theoretical RTP ≈ 94% at a 100-worship stake, validated over 10 million simulated spins — uncertified client-side RNG.'))) : null,

      /* ---- how it plays ---- */
      V.showHelp ? h('div', { style: MODAL_WRAP, onClick: V.closeModal },
        h('div', { style: Object.assign({ width: 'min(560px,94vw)' }, MODAL_CARD), onClick: function (e) { e.stopPropagation(); } },
          h('div', { style: Object.assign({}, EYEBROW, { color: 'var(--text-tertiary)' }) }, 'How it plays'),
          h('div', { style: Object.assign({}, PROSE, { fontSize: 16, lineHeight: 1.72, marginTop: 12 }) },
            h('p', { style: { margin: '0 0 12px' } },
              'Worship is the currency of the wheel, shown in whole worship — one for every cent. Fifteen gods ride five reels, one of each realm on every reel: ',
              h('span', { style: { color: '#15708C', fontWeight: 600 } }, 'Physical'), ', ',
              h('span', { style: { color: '#5A7D4C', fontWeight: 600 } }, 'Life'), ', and ',
              h('span', { style: { color: '#8A3033', fontWeight: 600 } }, 'Spirits'),
              ' — among items, Offerings, sacred places, and wandering mortals.'),
            h('p', { style: { margin: '0 0 12px' } }, 'The three sacred places wait above the wheel, unfound. Land one and it is charted; from then on, every mortal on the line leads ten more, divided among the charted places — and each god enthroned grants a boon in its own power, a wave, a bolt, a bloom, drawing a quarter to a full flock more to the charted place of its realm. Seat three gods of one realm, seat the Confluence, or let any one place quietly overflow, and the Worshipper Rite begins — mortals pour in far faster, and when the hymn fades every mortal offers 5 worship before the map is wiped clean.'),
            h('p', { style: { margin: 0, color: 'var(--text-secondary)', fontSize: 14, fontFamily: 'var(--font-ui)' } }, 'Played quietly: spins take at least 3.4 seconds, there is no autoplay, and a session note appears each hour with your time and totals. This is a design mockup, not a wagering product.')))) : null,

      /* ---- reality check ---- */
      V.showReality ? h('div', { style: Object.assign({}, MODAL_WRAP, { zIndex: 70 }) },
        h('div', { style: Object.assign({ width: 'min(420px,94vw)', textAlign: 'center' }, MODAL_CARD) },
          h('div', { style: Object.assign({}, EYEBROW, { color: 'var(--text-tertiary)' }) }, 'A quiet word'),
          h('div', { style: Object.assign({}, PROSE, { fontSize: 20, margin: '10px 0 6px' }) }, 'You have played for ' + V.sessionMins + ' minutes.'),
          h('div', { style: { fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 } }, V.sessionSpins + ' spins · ' + V.sessionStaked + ' staked · ' + V.sessionEarned + ' won.'),
          h('div', { style: { marginTop: 18, display: 'flex', justifyContent: 'center' } },
            h(Button, { variant: 'secondary', size: 'md', onClick: V.closeModal }, 'Continue')))) : null,

      /* ---- flying worshippers ---- */
      h('div', { style: { position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 40 } },
        V.flyers.map(function (f) {
          return h('img', { key: f.k, src: 'symbols-web/worshippers-1.png', alt: '', style: { position: 'absolute', width: 66, height: 66, left: f.x, top: f.y, transform: f.tr, opacity: f.op, transition: f.trans, filter: f.glow } });
        })),

      /* ---- rite fanfare ---- */
      V.hasFanfare ? h('div', { style: { position: 'fixed', inset: 0, zIndex: 55, background: 'rgba(26,23,20,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 } },
        h('div', { style: { position: 'relative', textAlign: 'center' } },
          h('div', { style: { position: 'absolute', left: '50%', top: '42%', width: 580, height: 580, borderRadius: '50%', background: 'radial-gradient(circle, rgba(184,134,11,0.5) 0%, rgba(184,134,11,0.16) 42%, transparent 70%)', animation: 'ffGlow 1500ms ease-in-out infinite alternate', pointerEvents: 'none' } }),
          h('div', { style: { position: 'relative', fontSize: 12, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--discover-gold)', animation: 'ffTitle 600ms cubic-bezier(0.16,1,0.3,1) 200ms both' } }, 'Worshipper Rite'),
          h('div', { style: Object.assign({}, PROSE, { position: 'relative', fontSize: 44, fontWeight: 700, color: '#FFF8E7', margin: '8px 0 4px', animation: 'ffTitle 700ms cubic-bezier(0.16,1,0.3,1) 350ms both' }) }, V.fanfareTitle),
          h('div', { style: Object.assign({}, PROSE, { position: 'relative', fontStyle: 'italic', fontSize: 17, color: 'rgba(247,245,242,0.85)', animation: 'ffTitle 700ms cubic-bezier(0.16,1,0.3,1) 550ms both' }) }, V.fanfareSub),
          h('div', { style: { position: 'relative', display: 'flex', justifyContent: 'center', gap: 22, marginTop: 28 } },
            V.fanfareGods.map(function (fg, i) {
              return h('div', { key: 'fg' + i, style: { animation: 'ffGod 800ms cubic-bezier(0.16,1,0.3,1) ' + fg.delay + 'ms both' } },
                h('img', { src: fg.img, alt: '', style: { width: 132, height: 132, borderRadius: 12, outline: '3px solid ' + fg.ring, outlineOffset: -1, boxShadow: '0 0 36px rgba(184,134,11,0.75)', animation: 'ffBob 1500ms ease-in-out ' + fg.bobDelay + 'ms infinite alternate' } }));
            })),
          h('div', { style: { position: 'relative', display: 'flex', flexWrap: 'wrap', justifyContent: 'center', alignItems: 'flex-end', gap: '6px 10px', marginTop: 28, maxWidth: 540, marginLeft: 'auto', marginRight: 'auto' } },
            V.fanfareWor.map(function (fw, i) {
              return h('img', { key: 'fw' + i, src: 'symbols-web/worshippers-1.png', alt: '', style: { width: fw.size, filter: 'drop-shadow(0 2px 6px rgba(0,0,0,0.55))', animation: 'ffWor 650ms cubic-bezier(0.16,1,0.3,1) ' + fw.delay + 'ms both, ffBob 850ms ease-in-out ' + fw.bobDelay + 'ms infinite alternate' } });
            })),
          h('div', { style: { position: 'relative', marginTop: 22, fontSize: 12, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(247,245,242,0.65)', animation: 'ffTitle 600ms ease 3400ms both' } }, 'The rite begins'))) : null,

      V.boonFxLayer,

      /* ---- preload ---- */
      h('div', { style: { display: 'none' } },
        (V.allImgs || []).map(function (im, i) { return h('img', { key: 'im' + i, src: im, alt: '' }); }))
    );
  }

  /* ---- mount ---- */
  var app = new Component({ startingWorship: 2000, fastSpins: false, realityCheckMinutes: 60 });

  function App() {
    var tick = React.useReducer(function (x) { return x + 1; }, 0);
    var force = tick[1];
    React.useEffect(function () {
      app._sub = function () { force(); };
      app.componentDidMount();
      return function () { app._sub = null; app.componentWillUnmount(); };
    }, []);
    return view(app.renderVals());
  }

  ReactDOM.createRoot(document.getElementById('root')).render(h(App));
})();
