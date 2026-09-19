# Handoff

Written 2026-08-27 at the point of pausing work; project list brought up to date
2026-09-19. The README covers *how* the site is built and how to add to it; this
covers where things stand, what is still open, and the reasoning behind choices
that would otherwise look arbitrary later.

## Status

Live at <https://donahue.us> — GitHub Pages from `LSD313/Portfolio`, `main`,
served from the repo root, so **merging to `main` is publishing**. Eight
projects in four sections, in the order the home page renders them:

| Section | Project | Kind | Size | Preview |
|---|---|---|---|---|
| Analytics | `datamat` | export, patched | 632 KB | yes |
| Analytics | `vehicle-performance-dashboard` | single file, data embedded | 13.6 MB | yes |
| HunnyDone | `hunnydone-app` | hand-written page + self-hosted MP4 | 13 MB | yes |
| HunnyDone | `hunnydone-pitch-deck` | hand-written viewer + 14 JPEG slides | 1.5 MB | yes |
| The Seeklore Universe | `seeklore-ereader` | export, patched, + book data | 3.9 MB | yes |
| The Seeklore Universe | `seeklore` | single file | 4.6 MB | yes |
| The Seeklore Universe | `seeklore-slots` | hand-ported, own art/fonts/runtime | 3.9 MB | yes |
| Tools | `meeting-scheduler` | hand-written | 80 KB | yes |

No longer "all self-contained single pages": five are one file (or one file plus
data), and three — `meeting-scheduler` and the two HunnyDone pages — are
hand-written and link the shared `tokens/` and `assets/fonts/`. What still holds
for every one of them is the constraint that matters: zero external requests.

Work happens on `claude/*` branches in worktrees under `.claude/worktrees/` and
lands by pull request; the pitch deck was
[LSD313/Portfolio#1](https://github.com/LSD313/Portfolio/pull/1).

## Open items

**1. `https://www.donahue.us` fails its TLS handshake.** Everything else about
the domain is correct: the apex serves over HTTPS, Enforce HTTPS is on, and
`http://www` already 301s to the apex. The single broken path is `www` over
HTTPS — which matters more than it sounds, because browsers increasingly
default to `https://` when someone types a bare hostname.

The cause looks like a DNS record type, not a GitHub setting. Re-saving the
custom domain *did* re-provision the certificate (validity dates moved from
Aug 23 to Aug 27), but it came back covering the apex only:

```
cert_domains=["donahue.us"]
X509v3 Subject Alternative Name: DNS:donahue.us
```

`www.donahue.us` is currently a **CNAME to `donahue.us`**. GitHub's documented
setup for an apex custom domain is A records on the apex plus a CNAME on `www`
pointing at **`lsd313.github.io`** — pointing `www` at the apex instead appears
to leave GitHub unable to verify it as a Pages host, so it is excluded from the
certificate request.

To try: change the `www` CNAME at the registrar from `donahue.us` to
`lsd313.github.io`, let DNS settle, then clear and re-save the custom domain in
Settings → Pages to force another provision. Re-tick Enforce HTTPS afterwards —
clearing the domain resets it. Verify with:

```bash
gh api repos/LSD313/Portfolio/pages --jq '.https_certificate.domains'
openssl s_client -connect donahue.us:443 -servername donahue.us </dev/null 2>/dev/null \
  | openssl x509 -noout -ext subjectAltName
```

Both should list `www.donahue.us` alongside the apex. Note the re-save takes
the site off HTTPS briefly, so pick a quiet moment. This is optional — the bare
domain works fine and is the URL worth sharing.

**2. The dashboard card preview is one palette behind.** It was captured before
the dark palette was neutralised, so it shows slightly warmer surfaces than the
live dashboard. Cosmetic, only visible side by side. A re-capture dropped at
`assets/vehicle-performance-dashboard.jpg` fixes it.

**3. The app video's audio has never been reviewed.** The picture was checked
frame by frame and edited (see the decision below), but nobody has listened to
it with publication in mind, and the cut at 5:06 lands mid-thought. The
HunnyDone business line is also on screen for most of the recording — the same
number that was on the deck's removed contact slide. It is a business number
for a company that is no longer trading, so it was left; blurring it needs
ffmpeg or an AVFoundation composition, and neither is set up here.

**4. The video has no captions.** There is no transcript to build a WebVTT track
from. If one is ever made, it is a `<track kind="captions">` inside the
`<video>` and a `.vtt` beside `intro.mp4`.

## Decisions worth not re-litigating

**HunnyDone material is edited for public display, and the sources stay out of
the repo.** The deck was written for investors and the video for customers;
neither was written to be posted. The deck lost its team and contact slides and
had a phone number masked in the image; the PDF is not committed because it
still carries all of that. The originals live in the iCloud archive under
`Pointe VC/Archive/HunnyDone Archive/`. The video lost 98 seconds (306–404 s of
the source) that showed two real contractors' names, numbers and quoted prices,
and was re-encoded so the footage is absent rather than hidden. The removed
slides were squashed out before the branch was first pushed, so they are not in
GitHub's history either — keep it that way by reviewing before the first push,
not after. **Every project page is self-contained and makes zero external
requests.** This is the constraint the whole site is built around, and it is
checked before anything ships. It is why the webfonts are vendored into
`assets/fonts/` rather than `@import`ed from Google, and why the dashboard's
user guide lost its font links. Verify a new page with: ```js
performance.getEntriesByType('resource').filter(r =>
!r.name.startsWith(location.origin)) ```

**The dashboard runs on fully synthetic data.** It began as a work artifact and
was rebuilt for public display: real vehicle hierarchy and segment taxonomy
(both public knowledge, and viewers need to recognise the names), but every
figure generated. The generator lives in the session scratchpad, not the repo —
if the dataset ever needs regenerating, that is the piece to reconstruct. The
splash screen states the terms the project is published under; leave it in.

**Vendored token files are copied verbatim and never edited.** Where a design
system's own values fail WCAG AA on these pages, the corrections live in a
documented override block in `style.css`. This keeps the vendored copies
re-copyable when the upstream design project changes.

**Uploaded images get derived, not used directly.** Screenshots arrive 2–3k px
and 0.7–1.5 MB; each is resized to 960 px (2× the widest the card renders) and
re-encoded as JPEG, landing at 110–170 KB. The full-size sources are removed
after deriving — they are in git history if needed.

## Gotchas that cost time

**CSS cascade in the dashboard.** The file carries *duplicated* `:root` token
blocks, so a later copy silently overrides earlier dark-theme values at equal
specificity. The dark palette therefore lives in a `:root[data-theme="dark"]`
block at the end of `<head>` — higher specificity *and* last in source. The
same trap caught the home page's accessibility overrides, which is why they are
scoped `:root:not([data-theme="dark"])`.

**There are two `</head>` tags** in the dashboard — the document's own and one
inside the user-guide template string. Inserting before the *last* one puts
your markup inside a JS string where it silently does nothing.

**Never string-replace across the whole dashboard file.** It mixes app code, a
vendored React build, and base64 blobs. A `"JDP" → "NLT"` replacement corrupted
the embedded font; a model rename rewrote React's internal key table
(`Esc: "Escape"` → the fictional name), breaking every Escape-key handler. Vault
the base64 blobs before any text substitution.

**GitHub Pages is case-sensitive.** An upload named `Seeklore.jpeg` will not
resolve a reference to `seeklore.jpg`, and the failure is silent — the image
just doesn't appear.

**Deleting an asset the markup points at breaks the live site.** This happened
twice while swapping screenshots. Uploading the replacement at the *same* path
avoids the window entirely.

**`git stash` without `stash pop`** left a session's work parked and the working
tree looking reverted. If something appears to have vanished, check
`git stash list` before re-doing it.

**A renamed image can show its old contents locally.** `git mv` keeps the
file's mtime, and `python3 -m http.server` answers `If-Modified-Since` from
mtime alone — so after renumbering the deck's slides the browser got
`304 Not Modified` and drew the wrong slide under the right filename. `touch`
the files and hard-refresh. GitHub Pages is unaffected; it validates on content.

**The app's automatic file preview is not the site.** Opening an `.html` file in
the editor's Browser pane loads it as a `data:` URL, so every relative path —
stylesheets, slides, the video — resolves to nothing and the page looks broken.
Only the single-file exports survive that. Check hand-written pages over HTTP.

**`python3 -m http.server` has no Range support.** Video seeking, and therefore
the chapter links on `hunnydone-app`, may not work against it. They work on
GitHub Pages.

**Port 4173 belongs to whichever session started first.** A second session (a
worktree, say) cannot reuse the `portfolio` launch config. A temporary
`autoPort` entry in `.claude/launch.json` running
`python3 -m http.server ${PORT}` works; do not commit it.

## Resuming

```bash
cd ~/Projects/donahue-portfolio
python3 -m http.server 4173     # then open http://localhost:4173
```

Adding a project is documented in the README. Fresh Claude Design exports need
`tools/patch-export.py` run against them — it fixes the title, chapter
alignment, and injects the back link, idempotently.

Contrast is checked on every change with an in-page sweep over all visible text,
compositing layered/translucent backgrounds and handling `oklch()` / `oklab()`
computed values. Both themes on both the home page and the dashboard currently
pass WCAG AA with zero failures; worth re-running after any palette work.
