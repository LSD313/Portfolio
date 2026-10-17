#!/usr/bin/env python3
"""Rebuild structure.csv (the generator's input) from the dataset embedded in the shipped dashboard.

    python3 tools/dashboard-data/extract_structure.py projects/vehicle-performance-dashboard/index.html

structure.csv has the same columns and rows as the embedded panel, with every metric cell replaced by 1 (filled)
or left empty, so it carries the hierarchy and the fill pattern but no figures. generate.py reads it, together with
tiers.csv and series_models.csv beside it, and writes a fresh synthetic panel. Run both from a scratch copy of this
directory if you do not want the output next to the sources.
"""
import base64, csv, gzip, io, os, re, sys

META = 11  # level .. premium_flag; everything after is a metric column


def main():
    src = sys.argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    with open(src, encoding="utf-8", errors="surrogateescape") as f:
        f.readline()
        line = f.readline()
    m = re.search(r'window\.PIN_SNAPSHOT_CSV_GZ="([A-Za-z0-9+/=]+)"', line)
    text = gzip.decompress(base64.b64decode(m.group(1))).decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    with open(os.path.join(here, "structure.csv"), "w", newline="\n") as out:
        w = csv.writer(out, lineterminator="\n")
        w.writerow(rows[0])
        for r in rows[1:]:
            w.writerow(r[:META] + ["1" if v != "" else "" for v in r[META:]])
    print("wrote structure.csv:", len(rows) - 1, "rows")


if __name__ == "__main__":
    main()
