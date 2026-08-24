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
    index.html                 exported app (design system + fonts bundled)
    books/                     book data — the export does NOT contain it
tools/
  patch-export.py              re-applies the fixes below to a fresh export
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

Project previews in `assets/` should be **16:10 or wider**. The card crops with
`object-fit: cover`, so a taller image loses its top and bottom — and a crop
line falling through the middle of something reads as the thumbnail bleeding
into the card text.

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
that happens to share the name.

**The export does not contain the books.** The app builds
`fetch('books/' + id + '/book.json')` at runtime, and the bundler only inlines
references it can resolve statically, so the book data has to sit on disk in
`books/`. Same for `books/sea-witch/cover.jpg`, which is applied as a CSS
`background-image`. Everything else — the runtime, React, the design system,
the fonts — is inlined.

`tools/patch-export.py` re-applies every fix below to a fresh export and is
idempotent, so re-running it is safe:

```bash
python3 tools/patch-export.py projects/seeklore-ereader/index.html "Seeklore eReader"
```

- **Title.** The export ships as `<title>Bundled Page</title>`, and the bundler
  replaces the whole document at boot, so a title set on the outer shell alone
  does not survive. One is injected into the `__bundler/template` payload too.

- **Chapter alignment.** `parseContent` started a new chapter on every `## `
  line and relied on their order matching `chapters[]`. That holds only when
  every heading is numbered. The Sea Witch also carries part dividers —
  `## Part One — The Court of Gold` — and each one pushed a phantom empty
  chapter that shifted the rest: chapter 2 ("The Ledger") rendered blank and
  chapter 3 ("The Survey") showed The Ledger's prose. The numbers in `## N`
  are already 1-based indices into `chapters[]`, so the parser keys off them
  and ignores unnumbered headings.

- **Blank reader on cold load.** The reading pane is gated behind `pw > 0`, and
  `pw` only becomes non-zero once `measure()` runs. The viewport ref gets one
  `requestAnimationFrame` attempt, and `measure()` returns early if the element
  has no width yet. The only *retrying* measure hangs off the content ref,
  which lives inside the `pw > 0` branch and so never mounts. One missed frame
  left the reader permanently blank — book loaded, prose parsed, nothing drawn.
  Two delayed retries are added to the ungated viewport ref.

- **Back link.** Project pages are full-screen apps with no route home, so a
  fixed "← Portfolio" control is appended and kept alive across the bundler's
  document swap. It sits top-centre — the one region free of app chrome on all
  three project pages. All three pages get this one.

- **BOOKS pruning.** Any book in the manifest with no data in `books/` is
  commented out, so it drops off the shelf instead of failing with
  "book.json HTTP 404" when opened. Currently that hides Treasure Island and
  The Count of Monte Cristo, whose `content.txt` files exceed the 256KB ceiling
  on the Claude Design MCP's file read and could only be retrieved truncated.
  Drop those two files into `books/<id>/` and re-run the script to restore them.

The title and chapter-alignment bugs are in the design project, so fixing them
in `Seeklore.dc.html` upstream would shrink this list.

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
