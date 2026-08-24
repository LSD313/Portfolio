#!/usr/bin/env python3
"""Apply the portfolio's fixes to a Claude Design standalone export.

A fresh export from the Seeklore design project needs the same three edits
every time. Run this on the exported .html before (or after) moving it into
projects/<name>/index.html:

    python3 tools/patch-export.py projects/seeklore-ereader/index.html

Every edit is idempotent, so re-running is safe and reports "already applied".

  1. Title. The export ships as <title>Bundled Page</title>. The bundler
     replaces the whole document at boot, so the outer shell's title does not
     survive — a <title> has to go into the __bundler/template payload too.

  2. Chapter alignment. parseContent starts a new chapter on every `## ` line
     and relies on their order matching chapters[]. That holds only when every
     heading is numbered. The Sea Witch also carries part dividers
     ("## Part One — The Court of Gold"), and each one pushes a phantom empty
     chapter that shifts the rest. The numbers in `## N` are already 1-based
     indices into chapters[], so key off them and ignore unnumbered headings.

  3. Back link. Project pages are full-screen apps with no route home, so a
     fixed "Portfolio" control is appended and kept alive across the bundler's
     document swap. It sits top-centre, which is the one region free of app
     chrome on all three project pages.

  4. Blank reader on cold load (bug fix). The reading pane is gated behind
     `pw > 0`, and `pw` only becomes non-zero once measure() runs. The viewport
     ref gets exactly one requestAnimationFrame attempt, and measure() returns
     early if the element has no width yet. The only *retrying* measure
     (setTimeout 200ms) hangs off the content ref -- which lives inside the
     `pw > 0` branch and therefore never mounts. So one missed frame leaves the
     reader permanently blank: book loaded, prose parsed, nothing rendered.
     Two delayed retries are added to the ungated viewport ref.

  5. BOOKS pruning (eReader only). The export does NOT contain the books: the
     app builds `fetch('books/' + id + '/book.json')` at runtime, and the
     bundler only inlines references it can resolve statically. So the book
     data has to sit on disk next to the page. Any book in the BOOKS manifest
     with no data on disk is commented out, so it drops off the shelf instead
     of erroring with "book.json HTTP 404" when opened. Add the missing files
     and re-run to bring a book back.

Fixing 1 and 2 in Seeklore.dc.html upstream would make them unnecessary here.
"""
import re
import sys

TITLE_DEFAULT = "Seeklore eReader"

BACK_LINK_JS = r"""
<script>
/* Portfolio back link. The bundler replaces the document at boot, so the
   element is re-appended if it goes missing. Kept out of the app's own
   chrome: bottom-left, above everything, and hidden when printing. */
(function () {
  var HREF = '../../';
  function make() {
    var a = document.createElement('a');
    a.id = '__portfolio_back';
    a.href = HREF;
    a.setAttribute('aria-label', 'Back to the portfolio');
    a.textContent = '← Portfolio';
    a.style.cssText = [
      'position:fixed', 'top:10px', 'left:50%', 'transform:translateX(-50%)',
      'z-index:2147483647',
      'display:inline-flex', 'align-items:center', 'gap:6px',
      'padding:7px 12px', 'border-radius:999px',
      'font:500 13px/1 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
      'letter-spacing:0.01em', 'text-decoration:none',
      'color:#F7F5F2', 'background:rgba(20,18,16,0.82)',
      'border:1px solid rgba(247,245,242,0.22)',
      'box-shadow:0 2px 10px rgba(0,0,0,0.35)',
      '-webkit-backdrop-filter:blur(8px)', 'backdrop-filter:blur(8px)',
      'transition:background 140ms ease,border-color 140ms ease'
    ].join(';');
    a.onmouseenter = function () {
      a.style.background = 'rgba(20,18,16,0.95)';
      a.style.borderColor = 'rgba(247,245,242,0.42)';
    };
    a.onmouseleave = function () {
      a.style.background = 'rgba(20,18,16,0.82)';
      a.style.borderColor = 'rgba(247,245,242,0.22)';
    };
    return a;
  }
  function ensure() {
    if (document.getElementById('__portfolio_back')) return;
    if (!document.body) return;
    document.body.appendChild(make());
  }
  ensure();
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', ensure);
  new MutationObserver(ensure).observe(
    document.documentElement, { childList: true, subtree: true });
})();
</script>
"""


def patch_title(s, title):
    done = []
    if "<title>Bundled Page</title>" in s:
        s = s.replace("<title>Bundled Page</title>", "<title>%s</title>" % title, 1)
        done.append("outer shell title")
    # the template payload stores markup escaped; `</` is written `</`
    anchor = '<meta name=\\"viewport\\" content=\\"width=device-width, initial-scale=1\\">'
    if "<title>%s<\\u002Ftitle>" % title in s:
        pass
    elif anchor in s:
        s = s.replace(anchor, anchor + '\\n<title>%s<\\u002Ftitle>' % title, 1)
        done.append("bundler template title")
    return s, done


def patch_parse_content(s):
    old = r"      if (/^## /.test(t)) { cur = []; out.push(cur); return; }"
    new = (r"      const h = /^##\\s+(\\d+)\\s*$/.exec(t);" "\\n"
           r"      if (h) { cur = []; out[parseInt(h[1], 10) - 1] = cur; return; }" "\\n"
           r"      if (/^##\\s/.test(t)) { cur = null; return; }")
    if new.split("\\n")[0] in s:
        return s, []
    if old not in s:
        return s, []
    return s.replace(old, new, 1), ["parseContent chapter alignment"]


VP_REF = ("this._vpEl = el; if (el) { if (this._ro) this._ro.observe(el); "
          "requestAnimationFrame(() => this.measure()); }")
VP_FIX = ("this._vpEl = el; if (el) { if (this._ro) this._ro.observe(el); "
          "requestAnimationFrame(() => this.measure()); "
          "setTimeout(() => this.measure(), 60); "
          "setTimeout(() => this.measure(), 250); }")


def patch_blank_reader(s):
    if VP_FIX in s:
        return s, []
    if VP_REF not in s:
        return s, []
    return s.replace(VP_REF, VP_FIX, 1), ["blank-reader measure retries"]


def prune_books(s, path):
    """Comment out BOOKS entries whose data is not on disk beside the page."""
    import json
    import os
    books_dir = os.path.join(os.path.dirname(os.path.abspath(path)), "books")
    if not os.path.isdir(books_dir) or "get BOOKS()" not in s:
        return s, []
    dropped = []
    # In the bundle the source is stored escaped, so a line break is the two
    # characters \ n rather than a real newline. Anchor on that instead of ^/$.
    entry = re.compile(r"(\\n\s*)(\{ id: '([a-z-]+)'[^\n]*?\},)(?=\\n)")
    for m in list(entry.finditer(s)):
        indent, line, bid = m.group(1), m.group(2), m.group(3)
        bj = os.path.join(books_dir, bid, "book.json")
        ok = os.path.isfile(bj)
        if ok:
            try:
                meta = json.load(open(bj, encoding="utf-8"))
            except Exception:
                ok = False
            else:
                cf = meta.get("contentFile")
                if cf and not os.path.isfile(os.path.join(books_dir, bid, cf)):
                    ok = False
                if not cf and not any(c.get("paras") for c in meta.get("chapters", [])):
                    ok = False
        if not ok:
            s = s.replace(m.group(0),
                          indent + "// " + line + "  // no data on disk", 1)
            dropped.append(bid)
    return s, (["pruned books with no data: " + ", ".join(dropped)] if dropped else [])


def patch_back_link(s):
    if "__portfolio_back" in s:
        return s, []
    i = s.rfind("</body>")
    if i < 0:
        return s, []
    return s[:i] + BACK_LINK_JS + s[i:], ["portfolio back link"]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else TITLE_DEFAULT
    s = open(path, encoding="utf-8", errors="surrogateescape").read()
    applied = []
    for fn in (lambda x: patch_title(x, title), patch_parse_content,
               patch_blank_reader, lambda x: prune_books(x, path),
               patch_back_link):
        s, done = fn(s)
        applied += done
    open(path, "w", encoding="utf-8", errors="surrogateescape").write(s)
    if applied:
        for a in applied:
            print("  applied:", a)
    else:
        print("  nothing to do — all fixes already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
