# Portfolio

> Picking this up after a break? See [HANDOFF.md](HANDOFF.md) for current
> status, open items, and the reasoning behind the choices here.

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
  nef-colors.css               colour tokens, vendored from New Enterprise Forum
  nef-typography.css           type scale, vendored
  nef-spacing.css              spacing, radii, layout, vendored
  nef-effects.css              shadows, borders, motion, vendored
  nef-fonts.css                @font-face for the self-hosted webfonts
assets/
  fonts/                       Instrument Sans, Mulish, Source Sans 3,
                               IBM Plex Mono (woff2)
  headshot.png                 hero avatar (optional — falls back to initials)
projects/
  vehicle-performance-dashboard/
    index.html                 self-contained project (data embedded)
  seeklore/
    index.html                 self-contained project (bundled assets)
  seeklore-ereader/
    index.html                 exported app (design system + fonts bundled)
  seeklore-slots/
    index.html                 The Votive Wheel — slot-machine game mockup
    app.js                     game logic + template, ported from the canvas
    symbols-web/               god, item, place and worshipper art
    fonts/  vendor/            self-hosted webfonts; React runtime
    books/                     book data — the export does NOT contain it
  meeting-scheduler/
    index.html                 hand-written app (uses tokens/ and assets/fonts/)
tools/
  patch-export.py              re-applies the fixes below to a fresh export
```

Most projects are standalone files. Two are not. `meeting-scheduler` is
hand-written rather than exported, so it links `tokens/` and `assets/fonts/`
the way the home page does instead of inlining copies of them. `seeklore-slots`
is implemented from a design canvas and keeps its art, fonts and runtime beside
it, so its own folder is self-contained.

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

The **New Enterprise Forum** system behind `meeting-scheduler` is vendored the
same way, as `tokens/nef-*.css`. Its `base.css` and `core.css` are deliberately
not copied: that page uses none of their `.nef-*` classes, and the dashboard set
the precedent of not shipping design-system code nothing calls. Its
`tokens/fonts.css` is the one file not copied verbatim — it `@import`s three
families from Google, so `nef-fonts.css` declares the same families, weights and
subsets against local woff2 instead.

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

## Sections

The grid is grouped into sections. Each is a `<section class="group">` holding a
`.section-head` (name + count) and its own `.projects` grid; an optional
`.group-note` sits under the heading. Adding a section means copying that block
and moving cards into it.

Counts are authored into the HTML so they are correct with JavaScript disabled,
then recomputed on load from the number of `.project` cards in each section — so
they cannot drift if you move a card and forget to bump the number. Keep the
authored value honest anyway; it is what a no-JS visitor sees.

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

## Note on The Votive Wheel

`seeklore-slots` implements `Seeklore Slots.dc.html` from the Seeklore Slot
Machine Game design project. The canvas is not shippable HTML: its markup
carries inline styles and `{{ }}` bindings, `<sc-for>`/`<sc-if>` control flow
and a `DCLogic` class, all resolved at runtime by `support.js`. Here the
template is ported to `React.createElement` and the bindings resolved at author
time, while the game logic — reel strips, paytable, the mortal economy, boons
and the Rite — is carried across essentially verbatim so behaviour matches the
canvas.

React is vendored into `vendor/` rather than dropped for vanilla DOM because the
flying worshippers animate by transitioning the *same* elements between phases;
that needs keyed reconciliation, not `innerHTML`. The design system's own
`fonts.css` `@import`s Google Fonts and ships an empty `assets/fonts`, so
Literata, Inter and JetBrains Mono are self-hosted in `fonts/` — the page makes
no external requests.

Art comes from the design project's `symbols-web/` set, rebuilt from the local
full-resolution cutouts at 288px (2x the largest on-screen render) because the
project's own copies are 360px and the panorama exceeds the API's 256 KiB read
cap.

It is a design mockup, not a wagering product, and says so on the page, in the
paytable and in the help panel. Those disclosures are part of the design —
leave them in.

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

- **Back link.** The exported project pages are full-screen apps with no route
  home, so a fixed "← Portfolio" control is appended and kept alive across the
  bundler's document swap. It sits top-centre — the one region free of app
  chrome on all three exported pages, and all three get this one.
  `meeting-scheduler` is hand-written and has a sticky header with room in it,
  so its back link is a real link in that header instead.

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

## Note on the Meeting Scheduler

`meeting-scheduler` implements `Meeting Scheduler.dc.html` from the **New
Enterprise Forum** design system. Unlike the eReader it is not an export: the
canvas file is a `DCLogic` class rendered by the same React runtime, and rather
than ship that runtime again the page is written out by hand the way the home
page was — static markup, `<sc-if>` becomes the `hidden` attribute, `style-hover`
and `style-focus` become real CSS rules, and `renderVals()` becomes a `render()`
that writes into the DOM. The domain logic — ICS parsing, the slot search, the
invitation builder — is carried over from the canvas as-is, except as noted
below. No build step, no dependencies, ~80KB total.

The app keeps everything in `localStorage` under `nef_scheduler_v1`; there is no
server, and none of the four pages here talk to one.

Four departures from the canvas, all deliberate:

- **The CORS proxy is gone.** `fetchICS` retried failed requests through
  `https://corsproxy.io/`. The Instructions tab tells people their secret
  calendar address "works like a password", and the Add tab promises "nothing is
  sent to any server" — routing that URL through a third party breaks both
  claims, and it is the same class of thing that was stripped out of the
  dashboard. The page now only ever requests the calendar host the user names.
  When that request fails, the UI already had the right answer: the upload and
  paste modes it points at by name.

- **Slot selection was dead.** `renderVals()` built a `selectHandler` for every
  slot card, but the template never bound it — nothing was clickable except
  "Book", so `hasSelectedSlot` could never become true and the whole "Create
  invitation" panel below was unreachable. The card is the select control here;
  Book stays as the one-click shortcut it already was.

- **Today was never searched.** `_computeSlots` advanced its cursor by a day
  whenever it had landed on or before now — always true for a search starting
  today — so today's remaining slots never appeared. The `ss <= now` test in the
  inner loop already rejects past slots, so the day skip is dropped.

- **The generated .ics was unescaped.** `generateICS` interpolated the meeting
  title and attendee names straight into `SUMMARY` and `ATTENDEE`, so a comma or
  semicolon in either silently split the property, and no line was folded at the
  75-octet limit. RFC 5545 escaping and folding are applied.

The first three are bugs in the design project; fixing them in
`Meeting Scheduler.dc.html` upstream would shorten this list.

Accessibility corrections live in a marked block at the top of the page's
`<style>`, on the same principle as `style.css`: the design system's muted text
tiers (`#7A7A7E`, `#9B9A9C`) and its brand orange as text or as a fill behind
white all fall below 4.5:1 at the sizes this page uses them. `#E75300` is kept
everywhere it is decoration rather than text. The tab bar, the mode switcher and
the instruction accordions also carry the ARIA roles and keyboard behaviour the
canvas's bare `<button>`s did not.
