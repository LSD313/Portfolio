# Portfolio

Personal project portfolio — a hand-written static site. No framework, no build step, no dependencies —
just HTML and CSS that a browser can open directly.

## Structure

```
index.html                     home page + project list
style.css                      the only stylesheet
projects/
  vehicle-performance-dashboard/
    index.html                 self-contained project (data embedded)
```

Every project is a folder under `projects/` containing its own `index.html`.
Linking to the folder (`projects/name/`) serves that file automatically.

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
