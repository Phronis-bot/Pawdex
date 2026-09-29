"""Build a breed training set from Wikidata + Wikimedia Commons (freely licensed photos).

Usage (inside the api container):
    python -m tools.breed_dataset cat [--per-breed 60]

Writes /data/breed_train/<species>/<Wikidata id>/NN.jpg plus a manifest.tsv with each
photo's source file, license and author (needed for attribution). Photos that are in
eval/ are skipped, so evaluation stays independent of training.
"""
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "PawdexDatasetBuilder/0.1 (breed recognition training set)"}
API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("/data/breed_train")
EVAL = Path(__file__).parent.parent / "eval"

BREED_CLASS = {"cat": "Q43577", "dog": "Q39367"}
# Wikidata items that are not a single breed, or whose Commons category is something else.
SKIP = {
    "Q4115865",  # Colorpoint Shorthair -> points at the Siamese category
    "Q42949",  # Rex mutation
    "Q12648",  # domestic short-haired cat -> the huge "Felis silvestris catus" category
    "Q42549",  # domestic long-haired cat
    "Q116193823",  # mixed breed cat (collected separately as the "mixed" class)
    "Q42600",  # squitten (a deformity, not a breed)
}
MIXED_CATEGORIES = {
    "cat": ["Mixed-breed cats", "Stray cats", "Feral cats", "Cats in Istanbul", "Tabby cats"],
    "dog": ["Mixed-breed dogs", "Stray dogs", "Street dogs", "Village dogs", "Pariah dogs"],
}


def get(url: str, attempts: int = 5) -> bytes:
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except urllib.error.URLError:
            if attempt == attempts - 1:
                raise
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("unreachable")


def api(**params) -> dict:
    time.sleep(1.0)  # be polite to Commons
    params |= {"format": "json", "formatversion": "2"}
    return json.loads(get(API + "?" + urllib.parse.urlencode(params)))


def breeds(species: str) -> list[tuple[str, str, str]]:
    query = f"""SELECT ?item ?label ?commons WHERE {{
      ?item wdt:P31 wd:{BREED_CLASS[species]} ; wdt:P373 ?commons .
      ?item rdfs:label ?label FILTER(lang(?label) = "en") }}"""
    url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(query)
    rows = json.loads(get(url))["results"]["bindings"]
    seen, out = set(), []
    for r in rows:
        qid = r["item"]["value"].rsplit("/", 1)[1]
        if qid in SKIP or qid in seen:
            continue
        seen.add(qid)
        out.append((qid, r["label"]["value"], r["commons"]["value"]))
    return out


def category_files(category: str, limit: int, depth: int = 2) -> list[str]:
    """File titles in a category and its subcategories (breadth-first)."""
    files, queue, visited = [], [(category, 0)], set()
    while queue and len(files) < limit * 2:
        cat, level = queue.pop(0)
        if cat in visited:
            continue
        visited.add(cat)
        data = api(action="query", list="categorymembers", cmtitle=f"Category:{cat}",
                   cmtype="file|subcat", cmlimit="200")
        for m in data.get("query", {}).get("categorymembers", []):
            title = m["title"]
            if title.startswith("Category:") and level < depth:
                queue.append((title.removeprefix("Category:"), level + 1))
            elif title.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                files.append(title)
    return files


def image_infos(titles: list[str]) -> list[dict]:
    infos = []
    for i in range(0, len(titles), 40):
        data = api(action="query", prop="imageinfo", titles="|".join(titles[i:i + 40]),
                   # Commons only serves (and caches) standard thumbnail widths; any
                   # other width is rate-limited: https://w.wiki/GHai
                   iiprop="url|extmetadata|mime", iiurlwidth="500")
        for page in data.get("query", {}).get("pages", []):
            info = (page.get("imageinfo") or [None])[0]
            if info and info.get("thumburl"):
                meta = info.get("extmetadata", {})
                infos.append({
                    "title": page["title"],
                    "url": info["thumburl"],
                    "license": meta.get("LicenseShortName", {}).get("value", "?"),
                    "artist": meta.get("Artist", {}).get("value", "?").replace("\t", " ").replace("\n", " ")[:200],
                })
    return infos


def eval_titles() -> set[str]:
    titles = set()
    for tsv in EVAL.glob("*/_sources.tsv"):
        for line in tsv.read_text(encoding="utf-8").splitlines():
            if "\t" in line:
                titles.add("File:" + line.split("\t", 1)[1].strip().replace("_", " "))
    return titles


def collect(species: str, key: str, label: str, categories: list[str], per_breed: int, skip: set[str], manifest) -> int:
    folder = OUT / species / key
    # Resume: skip breeds finished earlier (".done"), or collected by a run before that
    # marker existed, so a restart doesn't re-download them.
    if (folder / ".done").exists() or (folder.exists() and len(list(folder.glob("*.jpg"))) >= min(per_breed, 10)):
        return len(list(folder.glob("*.jpg")))
    folder.mkdir(parents=True, exist_ok=True)
    titles = []
    for cat in categories:
        titles += [t for t in category_files(cat, per_breed) if t.replace("_", " ") not in skip]
    titles = list(dict.fromkeys(titles))[: per_breed + 20]
    saved = 0
    for info in image_infos(titles):
        if saved >= per_breed:
            break
        try:
            time.sleep(1.0)  # at 0.3 s upload.wikimedia.org answered 429 every few files
            (folder / f"{saved:02d}.jpg").write_bytes(get(info["url"]))
        except Exception as e:  # noqa: BLE001 - one bad file shouldn't stop the run
            print(f"   skip {info['title']}: {e}", flush=True)
            continue
        manifest.write(f"{species}\t{key}\t{label}\t{saved:02d}.jpg\t{info['title']}\t{info['license']}\t{info['artist']}\n")
        manifest.flush()
        saved += 1
    (folder / ".done").touch()
    return saved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("species", choices=list(BREED_CLASS))
    parser.add_argument("--per-breed", type=int, default=60)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    skip = eval_titles()
    with open(OUT / "manifest.tsv", "a", encoding="utf-8") as manifest:
        n = collect(args.species, "mixed", "Mixed breed", MIXED_CATEGORIES[args.species],
                    args.per_breed * 3, skip, manifest)
        print(f"mixed: {n}", flush=True)
        for qid, label, category in breeds(args.species):
            n = collect(args.species, qid, label, [category], args.per_breed, skip, manifest)
            print(f"{qid} {label}: {n}", flush=True)


if __name__ == "__main__":
    main()
