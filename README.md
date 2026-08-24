# Portfolio

Personal project portfolio — a hand-written static site. No framework, no build step, no dependencies —
just HTML and CSS that a browser can open directly.

## Structure

```
index.html                     home page + project list
style.css                      layout, components, a11y overrides
tokens/
  pointe-colors.css            colour tokens, vendored from Pointe Analytics
  pointe-typography.css        type scale, vendored
  pointe-fonts.css             @font-face for the self-hosted webfonts
assets/
  fonts/                       Instrument Sans + IBM Plex Mono (woff2)
  headshot.png                 hero avatar (optional — falls back to initials)
projects/
  vehicle-performance-dashboard/
    index.html                 self-contained project (data embedded)
  seeklore/
    index.html                 self-contained project (bundled assets)
  seeklore-ereader/
    index.html                 self-contained project (app, design system,
                               five books and fonts all bundled)
```

Every project is a folder under `projects/` containing its own `index.html`.
Linking to the folder (`projects/name/`) serves that file automatically.

## Design

The home page implements `Portfolio.dc.html` from the **Pointe Analytics**
design system (a Claude Design canvas project). The canvas file keeps its
styles inline and its dynamic parts as `{{ }}` bindings resolved by a 70KB
React runtime; here those are lifted into CSS classes, `style-hover` becomes
real `:hover` rules, and the bindings are resolved at author time — so the page
is static HTML plus one small theme script.

`tokens/pointe-colors.css` and `tokens/pointe-typography.css` are copied
verbatim from that project — don't edit them; re-copy to update. Where the
system's own values fell below WCAG AA on this page, the corrections live in a
clearly-marked override block at the top of `style.css` rather than in the
vendored files.

The design's webfonts are self-hosted in `assets/fonts/` instead of loading
from Google, so the page makes no external requests at all — which is true of
every page on the site.

Theme defaults to dark, per the design, with a manual toggle in the footer that
persists to `localStorage`.

## Running it locally

```bash
python3 -m http.server 4173
```

Then open <http://localhost:4173>. Any static server works; this one ships
with macOS. Opening `index.html` via `file://` mostly works too, but a real
server avoids surprises with relative paths.

## Adding a project

1. Drop the folder into `projects/`.
2. Copy the `<a class="project">` block in `index.html` and edit the href,
   title, description and tags.

That's the whole workflow. There is nothing to rebuild.

## Deploying

The site is plain files, so hosting is swappable:

- **Your own server** — `rsync -avz --delete ./ user@host:/var/www/site/`,
  with Caddy or nginx in front. Most control, and TLS is automatic under Caddy.
- **GitHub Pages** — push and enable Pages. Zero admin, same files.

Nothing in the site depends on which you pick.

## Note on the Seeklore eReader

`seeklore-ereader` is a standalone export of `Seeklore.dc.html` from the
**Seeklore** design system — a different project from the `seeklore` card game
that happens to share the name. Everything is inlined: the Design Canvas
runtime, React, the design system, the fonts, and the full text of all five
books. It unpacks itself into blob URLs on load and makes no network requests
of any kind.

Two edits were made to the exported file:

- **Title.** The export ships as `<title>Bundled Page</title>`, and the
  bundler replaces the whole document at boot, so setting the title on the
  outer shell alone does not survive. A `<title>` was injected into the
  `__bundler/template` payload as well, which is what the browser tab and any
  bookmark end up reading.

- **Chapter alignment (bug fix).** `parseContent` started a new chapter on
  every `## ` line and relied on their order matching `chapters[]`. That holds
  only for a book whose headings are all numbered. The Sea Witch also carries
  part dividers — `## Part One — The Court of Gold` — and each one pushed a
  phantom empty chapter that shifted every chapter after it. In the export as
  received, Sea Witch chapter 2 ("The Ledger") rendered blank and chapter 3
  ("The Survey") showed The Ledger's prose, with the drift compounding at each
  divider. The numbers in `## N` are already 1-based indices into `chapters[]`,
  so the parser now keys off them and ignores unnumbered headings. Books whose
  headings are sequentially numbered parse exactly as before.

  This bug is in the design project too, so a fresh export will bring it back.
  Fixing `parseContent` in `Seeklore.dc.html` upstream would make future
  exports correct without patching.

## Note on the dashboard project

`vehicle-performance-dashboard` began as a work artifact and was rebuilt for
public display:

- All branding replaced with a placeholder brand ("Pointe Ventures").
- The embedded dataset is **entirely synthetic** — generated to match the
  original schema, hierarchy and time range, but every figure is invented.
  No real market data is present.
- A third-party analytics agent (which transmitted visitor email addresses)
  was removed, along with the email gate that fed it.
- An unused design-system bundle was stripped out.

The page makes no external network requests of any kind.
