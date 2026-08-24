# Why this directory exists

`index.html` is a self-contained export — the app, the design system, the
fonts and the full text of all five books are inlined, and the bundler serves
`books/<id>/book.json` and `content.txt` from inside the file.

`sea-witch/cover.jpg` is the one exception. The app applies it as a CSS
`background-image: url("books/sea-witch/cover.jpg")`, and the bundler only
inlines what it can resolve statically — a URL built at runtime in the `BOOKS`
manifest is invisible to it. So the browser resolves that path for real and it
has to exist on disk, or the Sea Witch shows a blank cover.

If a future export adds cover art for another book, its file goes here too,
under `books/<id>/`.
