---
name: design-tuner-loop
version: 1.0.0
agent_created: true
display_name: 可实时调参的设计稿
display_name_en: Live-Editable Design Mockups
description_zh: 把 AI 产出的设计稿变成你能拖滑块直接改的 HTML 页面——间距、字号、配色、圆角、画布宽度全部实时可调；勾选标注模式即可测量元素之间的真实间距与内边距；跨 700px 自动切换单列与双列。调完导出参数 JSON、可直接粘贴的 CSS，或一条含全部参数的分享链接。导出的数值就是最终落地的 CSS 值，Agent 按这组确切数字生成生产代码，无需 Figma 席位或 OAuth。
description_en: Turns a mockup into a self-contained HTML page whose spacing, type, colour and layout are live-editable from a side panel. Annotation mode measures the real gaps and paddings between elements. Export gives parameter JSON, paste-ready CSS, or a share link carrying every value. The exported numbers ARE the shipped CSS values, so code generation uses real numbers instead of guesses. No Figma seat or OAuth required.
description: This skill should be used when a UI design needs to be reviewed and fine-tuned before code is generated. It builds a self-contained HTML mockup whose spacing, type, colour and layout parameters are live-editable from a side panel, then exports those exact values as paste-ready CSS / JSON / share link. Delivers Figma-style precise editing with no licence, seat type, client whitelist or OAuth. 中文触发：设计调参、可调式设计稿、设计走查、把设计稿做成能改的、Figma 替代、前端设计确认门禁、设计稿先确认再写代码、我自己改页面细节。
when_to_use: Building a design-approval gate before code generation; the user wants to edit a design themselves; comparing Figma vs HTML for fine-grained editing; nudging spacing/type/colour rhythm on a mockup; a mockup is rejected as "not editable enough" and sliders are requested.
---

# Design tuner loop — make HTML mockups directly editable

## Why this exists

Users often say Figma is better than an HTML mockup because "I can go in and adjust the page precisely." Fair — a static HTML file gives a non-coder no editing surface at all. But the Figma route has costs people miss:

1. The Figma frame is **not the deliverable**. Every Figma edit means the agent re-reads the frame, re-interprets, and regenerates — lossy and slow. Once real components/state/data exist, the design file is stale.
2. Figma's "pixel precision" **has to be re-solved in CSS anyway** — responsive wrapping, text overflow, real font metrics (Figma's font ≠ the browser's), accessibility contrast. That precision gets translated once, and every translation loses something.
3. Figma's write path needs a paid Full seat + a whitelisted MCP client; read-only community servers need an API token. This pattern needs none of that.

Phase comparison — say this out loud to the user, don't oversell:

| Phase | Winner | Why |
|---|---|---|
| Early exploration ("does this layout even work") | Figma | Free-form dragging, multi-select, variants |
| Mid-stage detail (spacing rhythm, type scale, colour system) | **This pattern** | Exported numbers *are* the CSS values — lossless |
| Post-code tweaks | The code | Edit the real component |

**Be honest about what this can't do:** no dragging elements around, no multi-select align/distribute, no component instances/variants, no arbitrary-property editing, no comments/version history. If the user wants free-form manipulation, say plainly that's Figma's turf and offer the split (explore in Figma, tune + generate here).

## The pattern

One self-contained HTML file, five parts. Copy `assets/tuner-scaffold.html` and swap the mock content — it already implements all five.

1. **CSS custom properties on the mock root** (not `:root`) — so multiple mockups don't collide, and dark mode is a class swap that overrides the vars.
2. **A `MANIFEST` array** — the single source of truth for parameters. Controls, defaults, CSS writes, persistence, and exports are all generated from it.
3. **`buildControls()`** — auto-generates the panel from `MANIFEST`.
4. **`apply()`** — writes state onto the mock root via `style.setProperty`, refreshes readouts, runs `checkContrast()`, persists, redraws annotations. Bind to `input` (not `change`) so drags are live.
5. **Annotation mode + export** — measure real geometry; dump values for the agent.

### The manifest is the whole API

Adding a parameter is **one line**. Never hand-write a control, a readout, or an export branch.

```js
{group:'间距', key:'space', css:'--space', label:'组件间距',
 type:'range', min:4, max:36, step:1, unit:'px', def:16}

{group:'颜色', key:'accent', css:'--accent', label:'主色',
 type:'color', def:'#2f6fed'}

{group:'颜色', key:'theme', css:null, label:'底色',
 type:'seg', def:'light', options:[{v:'light',t:'浅色'},{v:'dark',t:'深色'}]}

{group:'布局', key:'mockW', css:'--mock-w', label:'画布宽度',
 type:'range', min:320, max:1200, step:10, unit:'px', def:390,
 presets:[{v:390,t:'手机'},{v:768,t:'平板'},{v:1100,t:'桌面'}]}
```

- `css:null` → the key is state-only (used by logic like the `.dark` toggle), skipped by CSS export.
- `type:'range'` gets `unit` appended; `'color'` and `'seg'` are written raw.
- `presets` adds quick-jump buttons under a slider (great for viewport widths).
- `def` is the documented default the reset button restores.

### Default parameter vocabulary

Start from this set; add or drop per page. Resist exposing everything — **the parameter set is a design decision, not an API.** Its boundary is whatever you can rewrite in a minute.

| Group | Key | CSS var | Range |
|---|---|---|---|
| 颜色 | accent | `--accent` | colour |
| 颜色 | theme | — | light / dark |
| 形状 | radius | `--radius` | 0–28 |
| 间距 | space | `--space` | 4–36 |
| 间距 | cardPad | `--card-pad` | 8–44 |
| 字体 | titleSize | `--title-size` | 18–40 |
| 字体 | bodySize | `--body-size` | 11–18 |
| 布局 | coverH | `--cover-h` | 80–280 |
| 布局 | mockW | `--mock-w` | 320–1200 + presets |

After the first pass, say to the user: "告诉我还缺什么，我加一个控件" — then actually add it.

## Persistence & sharing

Two layers, resolved in this order by `loadState()`:

1. **URL hash `#p=<base64(JSON)>`** — highest priority. Makes a link a complete snapshot of the design; regenerating it is the "复制链接" button.
2. **`localStorage`** (key `design-tuner-v2`) — survives reloads while the user is iterating.

```js
const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(state))));
const parsed = JSON.parse(decodeURIComponent(escape(atob(location.hash.slice(3)))));
```

`escape`/`unescape` are there on purpose — plain `btoa` chokes on non-ASCII, and this page is Chinese.

**Ordering trap:** `apply()` persists to localStorage, so the reset button must call `apply()` **first**, then `removeItem`. Otherwise reset silently re-writes the defaults and the "clear" is a no-op.

## Contrast validation (the bit Figma won't tell you)

`checkContrast()` computes the WCAG ratio of `accent` against white and warns inline:

- `< 3:1` → error: button text will be unreadable, darken the accent.
- `3:1 – 4.5:1` → warning: fine for large button text, don't use it for body copy.
- `≥ 4.5:1` → pass (AA body text).

This is the concrete payoff of tuning in the browser instead of a design tool: the warning is measured against the **real** text/background pair that will ship.

## Annotation mode (replaces Figma's measure tool)

Walk containers, diff `getBoundingClientRect()`, drop absolutely-positioned badges into the mock root (which must be `position: relative`).

Detect direction so both axes work — a row container needs horizontal gaps:

```js
const dir = getComputedStyle(group).flexDirection;
if (dir.indexOf('row') === 0) {   // ↔ horizontal
  const gap = Math.round(b.left - a.right);
  addBadge('↔ ' + gap, 'h', {left:(a.right-pr.left+gap/2)+'px', top:(a.top-pr.top+a.height/2)+'px'});
} else {                          // ↕ vertical
  const gap = Math.round(b.top - a.bottom);
  addBadge('↕ ' + gap, 'v', {left:'5px', top:(a.bottom-pr.top+gap/2)+'px'});
}
```

Also badge the mock's own `paddingLeft` and its rendered width. Measured containers: the top-level flex layout, every `.body`, `.navbar`, `.chips`, `.infolist` — i.e. every flex container on the page.

**Three mandatory details:**

- **Clear before redraw.** `clearAnnot()` runs first, or badges stack on every toggle (verified: repeated toggles went 20 → 30 badges when this was broken).
- **Redraw on `window.resize`.**
- **Wrap the badges in `pointer-events:none`** so they never intercept a click meant for the design.

## Responsive: use container queries, not media queries

The mock's width is itself a tunable (`--mock-w`), so the layout must react to the **mock's** width, not the window's:

```css
.mock{container-type:inline-size}
@container (min-width:700px){
  .layout{flex-direction:row}
  .layout > .cover{flex:1 1 46%;position:sticky;top:0}
}
```

This lets the user drag `画布宽度` from phone → tablet → desktop and watch a real breakpoint flip, in one browser tab, with no devtools.

### Trap: never put `width` in a CSS transition

`.mock` may transition `background` (the theme crossfade), but **must not transition `width`**. Verified in a real browser:

```
transition: background .15s, width .15s
  → getComputedStyle(mock).transitionProperty = "background, width"
  → inline --mock-w = 1100px  (value applied correctly)
  → mock.getBoundingClientRect().width = 390   ← geometry still the OLD value
  → remove the width transition → 1100         ← instantly correct
```

Why it matters more here than elsewhere: `apply()` calls `drawAnnot()` synchronously, so with a width transition the measurement runs against the *mid-transition* geometry. Badges then show wrong gap numbers, and because nothing redraws once the transition settles, **they stay wrong until the user touches another control**. In this tool geometry must be immediately deterministic — the whole point is measuring and exporting numbers. Dropping the width transition also makes the container-query flip instant, which is better feedback anyway.

The regression suite asserts this two ways: a direct check that `transitionProperty` excludes `width`, and a behavioural check that the geometry is correct immediately after a width change.

## Export contract

Emit **flat keys, numbers as numbers, explicit `unit`** — so the agent maps them onto CSS without parsing. Three buttons, one shared `readonly` textarea that `select()`s on click:

| Button | Output | Use |
|---|---|---|
| 导出参数 | `JSON.stringify(state, null, 2)` | Agent bakes values into production code |
| 复制 CSS | `:root { --radius: 24px; ... }` | Paste directly into a stylesheet |
| 复制链接 | `location.origin + pathname + '#p=' + b64` | Hand the exact design to anyone |

```json
{ "accent": "#2f6fed", "theme": "dark", "radius": 24, "space": 30,
  "titleSize": 34, "bodySize": 16, "coverH": 200, "mockW": 1100, "unit": "px" }
```

## Bringing it to a new page

1. Copy `assets/tuner-scaffold.html` to the target file.
2. Replace the mock markup with the real page's structure (keep `id="mock"` on the root).
3. Lift every value you want tunable into a CSS custom property on `.mock`, and reference it from the rules below (`padding: var(--card-pad)`, `gap: var(--space)`, …). **Anything that stays a hard-coded number can't be tuned.**
4. Trim `MANIFEST` to the properties that matter for this page; rename the groups/labels to the page's language.
5. If the page has a horizontal flex row, add that selector to the `groups` list in `drawAnnot()` so horizontal gaps get measured.
6. Open with `present_files` so it lands in the live preview panel.
7. After the user exports, **generate the code from those exact values** — closing the loop is what proves the workflow is lossless. Don't eyeball it.

## Regression tests

Two suites, because they catch different classes of bug. Run both after touching the scaffold.

### 1. jsdom — logic (`scripts/scaffold.test.js`)

41 assertions covering manifest→control generation, state→CSS var writes, dark toggle, WCAG verdicts, presets, annotation measurement (via a `getBoundingClientRect` stub) and badge clearing, all three exports, URL-hash replay, localStorage persistence, and reset.

```bash
cd <this-skill>/scripts
npm i jsdom
node scaffold.test.js                    # expect: 41 passed, 0 failed
node scaffold.test.js ./my-copy.html     # test any copy; exit code 1 on failure
```

Exits `2` if jsdom is missing, `1` on failure. Resolves its target from its own location, so no absolute paths are baked in.

### 2. Real Chromium — layout (`scripts/browser_verify.py`)

jsdom does **no real layout, ignores `@container`, and does not run CSS transitions** — so it cannot see the most dangerous class of bug in this tool. This suite drives an actual Edge/Chrome in headless mode:

```bash
python scripts/browser_verify.py                    # expect: 26 passed, 0 failed
python scripts/browser_verify.py path/to/copy.html   # any copy
```

It auto-detects Edge/Chrome, injects a probe into a temp copy (your file is never modified), runs `--headless=new --dump-dom`, parses the results and cleans up. Exits `2` if no browser is found.

What only this suite can catch:

- whether `@container` really flips `.layout` from `column` to `row`
- whether geometry is correct **immediately** after a width change (a CSS transition will lie to you here)
- whether annotation gaps are real, non-zero and in a sane range — and whether they follow the new width
- whether `getComputedStyle` actually resolves the theme switch and the accent colour to concrete `rgb()` values

Order matters inside the probe: all geometry assertions run **before** the probe disables the transition for the colour checks. Disabling it earlier silently masks the width-transition bug — that exact mistake produced a 25/25 false pass once.

### Always negative-verify

Break the behaviour an assertion targets, confirm the test actually FAILs, then restore. Confirmed working:

| Break this | Expected failures |
|---|---|
| Disable the URL-hash branch | jsdom: 4 |
| Stub out `setProperty` | jsdom: 7 |
| Remove the badge clear | jsdom: 2 |
| Put `width` back into the transition | Chromium: 3 |

## Checklist

- [ ] Vars declared on the mock root, with a `.dark` class that overrides them
- [ ] Controls generated from `MANIFEST` — no hand-written control markup
- [ ] Every control has a visible live value readout (users need to see the number to trust it)
- [ ] `input` events, not `change`
- [ ] `clearAnnot()` before every redraw; `window.resize` redraws
- [ ] Annotation badges are `pointer-events:none`
- [ ] `.mock{container-type:inline-size}` + `@container` breakpoints
- [ ] **`.mock` 的 transition 里没有 `width`**（否则几何读取会拿到过渡中间值）
- [ ] Reset restores defaults, clears the hash, **and** clears localStorage (after `apply()`)
- [ ] Export textarea is `readonly` + `select()`s on click
- [ ] Style native controls with `accent-color` rather than hand-rolling them
- [ ] A contrast warning exists and gives a real ratio
- [ ] Opened with `present_files`

## Working with the user

- **Expose only the parameters that matter**, then say out loud: "tell me what's missing and I'll add a control."
- Don't over-promise. Free-form manipulation is Figma's strength; say so and suggest the split.
- After they export, actually generate the code from those exact values.
