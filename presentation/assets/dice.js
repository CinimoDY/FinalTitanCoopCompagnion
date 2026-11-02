/* Enemy die (design/enemy-roll-design.md): the black reflective 3D cube, its flat and reduced-motion fallbacks,
   the Blessed/Cursed pair that waits for the players' pick, and the glow on the Attack Chart icon.
   Concatenated after fx.js into the same scope, so it uses that file's helpers and keeps its own names inside a block. */
(function () {
  // Side of the cube -> the die face on it, and the cube turn that brings that side to the front.
  const SIDES = [['front', 'blue'], ['right', 'green'], ['back', 'yellow'], ['left', 'red'], ['top', 'charge'], ['bottom', 'miss']];
  const TURN = { blue: [0, 0], green: [0, -90], yellow: [0, 180], red: [0, 90], charge: [-90, 0], miss: [90, 0] };
  const FACE_IDS = SIDES.map((s) => s[1]);
  const GLOW = { blue: '#4CC3FF', green: '#46F28A', yellow: '#FFE14D', red: '#FF5964', charge: '#FFD400', miss: '#9A96A0' };
  const CRACKS = '<svg class="crack" viewBox="0 0 100 100"><path d="M12 0 L30 38 L16 58 L38 100 M72 0 L62 34 L82 54 M100 18 L76 44 L90 70"/></svg>';

  FX.dice = [];  // the dice on the stage: { el, pop, face }

  function faceUrl(id) { return (FX.assets.dice || {})[id] || ''; }
  function tint(kind) { return kind === 'blessed' || kind === 'cursed' ? kind : ''; }

  function removeDice(restingOnly) {
    FX.dice = FX.dice.filter((d) => {
      if (restingOnly && !d.el.classList.contains('resting')) return true;
      d.el.remove();
      return false;
    });
  }
  // A rerun with nothing left to pick means the pair is stale (picked elsewhere, undone, or the turn moved on).
  FX.onReceive = function (payload) {
    // The pick's own rerun still needs the pair on stage: its cue drops one die and pops the other.
    const picking = (payload.cues || []).some((c) => c.kind === 'roll_pick' && !FX.seen.has(c.id));
    if (!(payload.extra && payload.extra.pending_pick) && !picking) removeDice(true);
  };

  // A closed cube with smooth rounded edges, built from flat parts around the center:
  // 6 faces (the card icons), 12 edges of EDGE_STEPS strips each (a quarter cylinder of radius r), 8 corner caps
  // (the sphere octants) and a black core, so no gap ever shows the stage through the die.
  const EDGE_STEPS = 6;
  const ROT_FACE = { front: '', back: 'rotateY(180deg)', right: 'rotateY(90deg)', left: 'rotateY(-90deg)', top: 'rotateX(90deg)', bottom: 'rotateX(-90deg)' };
  const AXIS = ['', 'rotateZ(90deg)', 'rotateY(90deg)'];  // edges along x, y, z

  function part(cls, left, top, w, h, transform) {
    return '<i class="' + cls + '" style="left:' + left.toFixed(2) + 'px;top:' + top.toFixed(2) + 'px;width:' + w.toFixed(2) + 'px;height:' + h.toFixed(2) + 'px;transform:' + transform + '"></i>';
  }

  function cubeParts(size) {
    const r = size * 0.13, c = size / 2 - r, half = size / 2;
    const flat = size - 2 * r;  // side of the flat part of a face
    const step = 90 / EDGE_STEPS;
    const out = [];
    // Edge strips: tangent to the quarter circle, each one a little wider than its arc so neighbors overlap.
    const sw = 2 * r * Math.sin((step / 2) * Math.PI / 180) + 1.2, reach = r * Math.cos((step / 2) * Math.PI / 180);
    AXIS.forEach((axis) => {
      for (let k = 0; k < 4; k++) {
        for (let i = 0; i < EDGE_STEPS; i++) {
          const a = step / 2 + i * step;
          out.push(part('ft-die-edge e' + i, half - (flat + 1.2) / 2, half - sw / 2, flat + 1.2, sw,
            (axis ? axis + ' ' : '') + 'rotateX(' + k * 90 + 'deg) translate3d(0,' + -c + 'px,' + c + 'px) rotateX(' + a + 'deg) translateZ(' + reach + 'px)'));
        }
      }
    });
    // Corner caps: a disc on the diagonal plane through the three strip ends closes the last gap.
    const cap = r * 0.84;
    [-1, 1].forEach((sx) => [-1, 1].forEach((sy) => [-1, 1].forEach((sz) => {
      const yaw = Math.atan2(sx, sz) * 180 / Math.PI, pitch = Math.asin(-sy / Math.sqrt(3)) * 180 / Math.PI;
      out.push(part('ft-die-corner', half - cap, half - cap, cap * 2, cap * 2,
        'translate3d(' + sx * c + 'px,' + sy * c + 'px,' + sz * c + 'px) rotateY(' + yaw + 'deg) rotateX(' + pitch + 'deg) translateZ(' + r * 0.577 + 'px)'));
    })));
    // Core: three black squares through the center.
    const core = size - r;
    ['', 'rotateX(90deg)', 'rotateY(90deg)'].forEach((rot) => out.push(part('ft-die-core', half - core / 2, half - core / 2, core, core, rot || 'none')));
    return { html: out.join(''), flat, half };
  }

  function cubeEl(face, kind, size) {
    const g = cubeParts(size);
    const f = g.flat + 1.2;
    const sides = SIDES.map(([side, id]) => {
      const img = faceUrl(id) && id !== 'miss' ? '<img alt="" src="' + esc(faceUrl(id)) + '">' : '';
      return '<div class="ft-die-face s-' + side + '" style="left:' + (g.half - f / 2).toFixed(2) + 'px;top:' + (g.half - f / 2).toFixed(2) + 'px;width:' + f.toFixed(2) + 'px;height:' + f.toFixed(2) +
        'px;transform:' + ROT_FACE[side] + ' translateZ(' + g.half + 'px)">' + img + (kind === 'cursed' ? CRACKS : '') + '<i class="sheen"></i></div>';
    }).join('');
    return '<div class="ft-die-fly"><div class="ft-die-tilt"><div class="ft-die-cube">' + g.html + sides + '</div></div></div>';
  }

  function flatEl(face) {
    const img = faceUrl(face) && face !== 'miss' ? '<img alt="" src="' + esc(faceUrl(face)) + '">' : '';
    return '<div class="ft-die-fly"><div class="ft-die-tile">' + img + '</div></div>';
  }

  // One die on the stage: pos (x travel) > pop (scale) > fly (height). Returns the record kept in FX.dice.
  function makeDie(face, kind, size, spot, cube) {
    const el = D.createElement('div');
    el.className = 'ft-die-pos ' + (cube ? 'cube ' : 'flat ') + tint(kind);
    el.style.cssText = 'left:' + (spot.x - size / 2) + 'px;top:' + (spot.y - size / 2) + 'px;width:' + size + 'px;height:' + size + 'px;--s:' + size + 'px';
    el.innerHTML = '<i class="ft-die-shadow"></i><div class="ft-die-pop">' + (cube ? cubeEl(face, kind, size) : flatEl(face)) + '</div>';
    root.appendChild(el);
    const die = { el, pop: el.querySelector('.ft-die-pop'), fly: el.querySelector('.ft-die-fly'), shadow: el.querySelector('.ft-die-shadow'),
      cube: el.querySelector('.ft-die-cube'), tile: el.querySelector('.ft-die-tile'), face, size, spot };
    FX.dice.push(die);
    return die;
  }

  function burstAt(spot, size, color) {
    const b = div('ft-die-burst', '', { left: spot.x - size * 1.1 + 'px', top: spot.y - size * 1.1 + 'px', width: size * 2.2 + 'px', height: size * 2.2 + 'px' });
    b.style.setProperty('--burst', color);
    return anim(b, C.reduced ? [{ opacity: 0 }, { opacity: 0.8, offset: 0.3 }, { opacity: 0 }]
      : [{ transform: 'scale(.2) rotate(-20deg)', opacity: 0.95 }, { transform: 'scale(1.1) rotate(8deg)', opacity: 0.9, offset: 0.5 }, { transform: 'scale(1.3) rotate(12deg)', opacity: 0 }],
    { duration: 520, easing: 'ease-out' }).then(() => b.remove());
  }

  // The Attack Chart icon lights up: a bright outline glow, local to that one icon.
  function iconGlow(r, icon, color) {
    const rad = icon.r * r.w * 1.12;
    const g = div('ft-fx-iconglow', '', { left: r.x + icon.x * r.w - rad + 'px', top: r.y + icon.y * r.w - rad + 'px', width: rad * 2 + 'px', height: rad * 2 + 'px' });
    g.style.setProperty('--glow', color);
    const frames = C.reduced
      ? [{ opacity: 0 }, { opacity: 1, offset: 0.08 }, { opacity: 1, offset: 0.82 }, { opacity: 0 }]
      : [{ opacity: 0, transform: 'scale(.8)' }, { opacity: 1, transform: 'scale(1.22)', offset: 0.07 }, { transform: 'scale(1)', offset: 0.17 },
        { transform: 'scale(1.1)', offset: 0.28 }, { transform: 'scale(1)', offset: 0.38 }, { opacity: 1, transform: 'scale(1)', offset: 0.8 }, { opacity: 0, transform: 'scale(1.05)' }];
    return anim(g, frames, { duration: 3200 }).then(() => g.remove());
  }

  // ---------------------------------------------------------------- the throw
  function startPoint() {
    const btn = rectOf(q('[class*="st-key-ft_enemy_roll"]')) || rectOf(q('.st-key-ft_caption'));
    return btn ? center(btn) : { x: W.innerWidth * 0.2, y: W.innerHeight * 0.8 };
  }

  // A black glossy cube that tumbles in an arc, bounces twice and settles on its result face.
  async function throwCube(die, from, delay) {
    const { el, pop, fly, shadow, cube, spot, size } = die;
    const dx = from.x - spot.x, dy = from.y - spot.y;
    const [tx, ty] = TURN[die.face];
    const turns = 360 * (2 + Math.floor(rnd(0, 2)));
    const end = 'rotateX(' + (tx + turns) + 'deg) rotateY(' + (ty - turns) + 'deg) rotateZ(0deg)';
    cube.style.transform = end;
    const T = 1150, d = delay;
    el.style.visibility = 'hidden';
    await wait(d);
    el.style.visibility = '';
    anim(el, [{ transform: 'translateX(' + dx + 'px)' }, { transform: 'translateX(0)', offset: 0.78, easing: 'cubic-bezier(.3,.7,.4,1)' }, { transform: 'translateX(' + rnd(8, 18) + 'px)' }],
      { duration: T, easing: 'linear' });
    anim(pop, [{ transform: 'scale(.45)' }, { transform: 'scale(1)', offset: 0.42 }, { transform: 'scale(1)' }], { duration: T });
    anim(fly, [
      { transform: 'translateY(' + dy + 'px)', easing: 'ease-out' },
      { transform: 'translateY(' + (dy - size * 1.6) + 'px)', offset: 0.17, easing: 'ease-in' },
      { transform: 'translateY(0)', offset: 0.42, easing: 'ease-out' },
      { transform: 'translateY(' + -size * 0.5 + 'px)', offset: 0.58, easing: 'ease-in' },
      { transform: 'translateY(0)', offset: 0.72, easing: 'ease-out' },
      { transform: 'translateY(' + -size * 0.14 + 'px)', offset: 0.84, easing: 'ease-in' },
      { transform: 'translateY(0)', offset: 0.92 }, { transform: 'translateY(0)' }], { duration: T });
    anim(shadow, [{ opacity: 0, transform: 'scale(.3)' }, { opacity: 0, offset: 0.3 }, { opacity: 0.75, transform: 'scale(1)', offset: 0.42 }, { opacity: 0.4, transform: 'scale(.7)', offset: 0.58 },
      { opacity: 0.75, transform: 'scale(1)', offset: 0.72 }, { opacity: 0.75, transform: 'scale(1)' }], { duration: T });
    anim(cube, [{ transform: 'rotateX(' + rnd(0, 360) + 'deg) rotateY(' + rnd(0, 360) + 'deg) rotateZ(' + rnd(-50, 50) + 'deg)' }, { transform: end }],
      { duration: T * 0.94, easing: 'cubic-bezier(.12,.6,.22,1)' });
    // The specular highlight sweeps across every face while the cube turns.
    el.querySelectorAll('.sheen').forEach((s, i) => anim(s, [{ transform: 'translateX(-90%)' }, { transform: 'translateX(90%)' }],
      { duration: T / 2.5, iterations: 3, delay: i * 60, easing: 'ease-in-out', fill: 'both' }));
    setTimeout(() => sfx('thud'), (d + T * 0.42) * C.k);
    setTimeout(() => sfx('thud'), (d + T * 0.72) * C.k);
    await wait(T);
  }

  async function throwFlat(die, from, delay) {
    const { el, pop, tile, spot } = die;
    const dx = from.x - spot.x, dy = from.y - spot.y;
    el.style.visibility = 'hidden';
    await wait(delay);
    el.style.visibility = '';
    const img = tile.querySelector('img');
    let ticker = null;
    if (img) {
      ticker = setInterval(() => { img.src = faceUrl(pick(FACE_IDS.filter((f) => f !== 'miss'))); }, 70 * C.k);
    }
    await anim(pop, [{ transform: 'translate(' + dx + 'px,' + dy + 'px) rotate(0deg) scale(.5)', filter: 'blur(3px)' },
      { transform: 'translate(0,0) rotate(540deg) scale(1)', filter: 'blur(0)' }], { duration: 700, easing: 'cubic-bezier(.2,.8,.3,1)' });
    clearInterval(ticker);
    if (img) img.src = faceUrl(die.face);
    sfx('thud');
  }

  function fadeOut(dice, ms) {
    return Promise.all(dice.map((d) => anim(d.el, [{ opacity: 1 }, { opacity: 0 }], { duration: ms || 320 }).then(() => {
      d.el.remove();
      FX.dice = FX.dice.filter((x) => x !== d);
    })));
  }

  // The pair waits on the stage until the players pick one: click it, or use the buttons in the caption box.
  function rest(dice) {
    dice.forEach((d, i) => {
      d.el.classList.add('resting');
      d.el.title = d.face;
      d.el.onclick = () => {
        const b = q('[class*="st-key-ft_pick_' + i + '_"] button');
        if (b) b.click();
      };
    });
  }

  HANDLERS.roll = async (c) => {
    const p = c.params;
    removeDice(false);
    const faces = p.faces || [];
    const r = imgRect(cardEl(c.target));
    if (!faces.length || !r) return;  // rolled on the table: the tracker is all there is
    const from = startPoint();
    const kind = p.token === 'blessed' || p.token === 'cursed' ? p.token : '';
    const size = Math.max(64, Math.min(124, r.w * 0.17));
    const gap = size * 0.7;
    const cy = r.y + r.h * 0.62, cx = r.x + r.w * (faces.length === 1 ? 0.3 : 0.32);
    const spots = faces.map((f, i) => ({ x: cx + (faces.length === 1 ? 0 : (i ? gap : -gap)), y: cy }));
    const full = !C.low && !C.reduced;
    const center0 = { x: cx, y: cy };

    if (C.reduced) {
      // Reduced motion: the face appears over the Roll button with a short fade. No travel, no tumble.
      const btn = rectOf(q('[class*="st-key-ft_enemy_roll"]'));
      const s = Math.min(70, btn ? btn.h * 1.3 : 64);
      const base = btn ? center(btn) : center0;
      const dice = faces.map((f, i) => makeDie(f, kind, s, { x: base.x + (faces.length === 1 ? 0 : (i ? s * 0.6 : -s * 0.6)), y: btn ? btn.y - s * 0.7 : base.y }, false));
      await Promise.all(dice.map((d) => anim(d.el, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 })));
      FX.diceSpot = center0;
      if (p.pending) { rest(dice); return; }
      await wait(1100);
      await fadeOut(dice, 300);
      return;
    }

    if (full) {
      // Wind-up: the enemy card shakes and drums before the throw.
      sfx('drumroll');
      await anim(cardEl(c.target), [{ transform: 'none' }, { transform: 'translate(-6px,2px) rotate(-1.5deg)', offset: 0.2 }, { transform: 'translate(6px,-2px) rotate(1.5deg)', offset: 0.4 },
        { transform: 'translate(-4px,1px)', offset: 0.6 }, { transform: 'translate(3px,0)', offset: 0.8 }, { transform: 'none' }], { duration: 340 });
      word(p.word, from.x, from.y - 50, { burst: '#E63946', color: '#FFD400', size: 2.2, dur: 700, rot: -6 });
    }
    streak(from, spots[0]);

    const dice = faces.map((f, i) => makeDie(f, kind, size, spots[i], full));
    FX.diceSpot = center0;
    if (full) {
      if (p.charged) {
        // Charge is flipped: the next Charge is the Ultimate, so the die crackles on its way.
        [0.2, 0.5, 0.8].forEach((k) => setTimeout(() => bolt(spots[0].x + rnd(-size, size), spots[0].y - size * 2, spots[0].y + size * 0.4), 1150 * k * C.k));
      }
      await Promise.all(dice.map((d, i) => throwCube(d, from, i * 130)));
    } else {
      await Promise.all(dice.map((d, i) => throwFlat(d, from, i * 120)));
    }

    // Landed: the counting die pops with a burst in its face color.
    const color = p.color || '#FFD400';
    if (p.pending) {
      rest(dice);
      dice.forEach((d) => anim(d.pop, [{ transform: 'scale(1)' }, { transform: 'scale(1.18)', offset: 0.4 }, { transform: 'scale(1.05)' }], { duration: 340, fill: 'forwards' }));
      return;
    }
    burstAt(center0, size, color);
    sfx('pow');
    const pops = dice.map((d) => anim(d.pop, [{ transform: 'scale(1)' }, { transform: 'scale(1.3)', offset: 0.4 }, { transform: 'scale(1.18)' }], { duration: 380, fill: 'forwards' }));
    if (p.doubles) {
      word(p.doubles_word, center0.x, center0.y - size * 1.3, { burst: '#E63946', color: '#FFD400', size: 3, dur: 1100, rot: -5 });
      dice.forEach((d) => anim(d.el, [{ filter: 'brightness(1)' }, { filter: 'brightness(2.2)', offset: 0.3 }, { filter: 'brightness(1)' }], { duration: 500, iterations: 2 }));
    }
    if (full && p.taunt) bubble(p.taunt, r);
    await Promise.all(pops);
    await wait(p.doubles ? 1000 : 700);
    await fadeOut(dice, 320);
  };

  // The players picked one of the two dice: the other drops away, the kept one pops.
  HANDLERS.roll_pick = async (c) => {
    const pair = FX.dice.filter((d) => d.el.classList.contains('resting'));
    pair.forEach((d) => { d.el.classList.remove('resting'); d.el.onclick = null; });
    if (pair.length !== 2) return;
    const keep = pair[c.params.pick], drop = pair[1 - c.params.pick];
    anim(drop.el, [{ opacity: 1, filter: 'grayscale(0)', transform: 'none' }, { opacity: 0, filter: 'grayscale(1)', transform: C.reduced ? 'none' : 'translateY(80px) rotate(24deg) scale(.7)' }], { duration: 600, easing: 'ease-in' })
      .then(() => { drop.el.remove(); FX.dice = FX.dice.filter((x) => x !== drop); });
    const spot = keep.spot;
    burstAt(spot, keep.size, GLOW[keep.face] || '#FFD400');
    sfx('pow');
    await anim(keep.pop, [{ transform: 'scale(1.05)' }, { transform: 'scale(1.38)', offset: 0.4 }, { transform: 'scale(1.18)' }], { duration: 380, fill: 'forwards' });
    word(tx('roll_pick', 'KEPT!'), spot.x, spot.y - keep.size * 1.2, { burst: '#FFC300', color: '#fff', size: 2.2, dur: 800 });
    await wait(800);
    await fadeOut([keep], 320);
  };

  // Where to look: the icon glow on the card, the Charge switch pulse, or the Miss puff.
  HANDLERS.roll_glow = async (c) => {
    const p = c.params;
    const r = imgRect(cardEl(c.target));
    const spot = FX.diceSpot || (r && { x: r.x + r.w * 0.3, y: r.y + r.h * 0.6 });
    if (p.icon && r) {
      iconGlow(r, p.icon, p.color);
      return wait(600);
    }
    if (p.face === 'charge') {
      const row = q('.st-key-ft_charge_row');
      if (row) {
        row.classList.add('ft-roll-pulse');
        setTimeout(() => row.classList.remove('ft-roll-pulse'), 3200 * C.k);
      }
      sfx('zap');
      if (spot) await word(p.word, spot.x, spot.y - 70, { color: '#FFD400', burst: p.ultimate ? '#E63946' : '#9D4EDD', size: 3.2 });
    } else if (p.face === 'miss' && spot) {
      await word(p.word, spot.x, spot.y - 70, { puff: true, color: '#d6d6dc', size: 3 });
    }
  };
})();
