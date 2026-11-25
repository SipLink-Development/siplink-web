"""One-off: turns the old /location WordPress posts into Sanity drafts for review.

Reads WordPress through the local viewer (.claude/old-location-proxy.mjs on :4321),
because www.siplink.in no longer points at the old cPanel server.
Run from studio/: python migration/build-location-posts.py
Then: sanity dataset import migration/location-posts.ndjson production --missing
"""
import html
import io
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image

WP = "http://localhost:4321/location/wp-json"
HERE = Path(__file__).parent
IMAGES = HERE / "location-images"
MIN_WIDTH = 1200  # studio/schemaTypes/image-limits.ts blocks publishing below this


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"user-agent": "Mozilla/5.0"})) as r:
        return r.read()


def site_href(href):
    href = re.sub(r"^http://localhost:4321/location/([^/?#]+)/?", r"/blog/\1", href)
    return href.replace("http://localhost:4321", "https://www.siplink.in")


def full_size(src):
    return re.sub(r"-\d+x\d+(\.\w+)$", r"\1", src)


class Blocks(HTMLParser):
    """WordPress post HTML to Portable Text: paragraphs, h2/h3, lists, bold, italic, links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.images, self.lists, self.marks = [], [], [], []
        self.block = None
        self.n = 0
        self.skip = 0  # inside figcaption, script or style

    def key(self):
        self.n += 1
        return f"k{self.n:x}"

    def open_block(self, style="normal", **extra):
        self.close_block()
        self.block = {"_type": "block", "_key": self.key(), "style": style, "markDefs": [], "children": [], **extra}

    def close_block(self):
        b = self.block
        if b and "".join(c["text"] for c in b["children"]).strip():
            b["children"][0]["text"] = b["children"][0]["text"].lstrip()
            b["children"][-1]["text"] = b["children"][-1]["text"].rstrip()
            self.blocks.append(b)
        self.block = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("figcaption", "script", "style"):
            self.skip += 1
        elif tag in ("ul", "ol"):
            self.close_block()
            self.lists.append("number" if tag == "ol" else "bullet")
        elif tag == "li":
            self.open_block(listItem=self.lists[-1] if self.lists else "bullet", level=max(1, len(self.lists)))
        elif tag == "p" or tag == "tr":
            self.open_block()
        elif tag == "blockquote":
            self.open_block("blockquote")
        elif re.fullmatch(r"h[1-6]", tag):
            self.open_block("h2" if tag in ("h1", "h2") else "h3")
        elif tag in ("strong", "b"):
            self.marks.append("strong")
        elif tag in ("em", "i"):
            self.marks.append("em")
        elif tag == "a" and a.get("href") and not a["href"].endswith("#"):
            if not self.block:
                self.open_block()
            k = self.key()
            self.block["markDefs"].append({"_type": "link", "_key": k, "href": site_href(a["href"])})
            self.marks.append(k)
        elif tag == "a":
            self.marks.append(None)
        elif tag == "img" and a.get("src"):
            self.images.append({"src": full_size(a["src"]), "alt": a.get("alt", "")})
        elif tag in ("td", "th") and self.block and self.block["children"]:
            self.handle_data(" | ")

    def handle_endtag(self, tag):
        if tag in ("figcaption", "script", "style"):
            self.skip -= 1
        elif tag in ("ul", "ol"):
            self.close_block()
            if self.lists:
                self.lists.pop()
        elif tag in ("p", "li", "blockquote", "tr") or re.fullmatch(r"h[1-6]", tag):
            self.close_block()
        elif tag in ("strong", "b", "em", "i", "a") and self.marks:
            self.marks.pop()

    def handle_data(self, data):
        if self.skip:
            return
        text = re.sub(r"\s+", " ", data)
        if not text.strip() and not (self.block and self.block["children"]):
            return
        if not self.block:
            self.open_block()
        self.block["children"].append({"_type": "span", "_key": self.key(), "text": text, "marks": [m for m in self.marks if m]})


def save_image(src, slug):
    img = Image.open(io.BytesIO(get(src))).convert("RGB")
    if img.width < MIN_WIDTH:
        # shortcut: WordPress images are 1000 px; upscaled to pass the Studio's 1200 px rule. Replace with sharper originals when the SEO team has them.
        img = img.resize((MIN_WIDTH, round(img.height * MIN_WIDTH / img.width)), Image.LANCZOS)
    IMAGES.mkdir(exist_ok=True)
    path = IMAGES / f"{slug}.jpg"
    img.save(path, "JPEG", quality=88, optimize=True)
    return path


def seo(slug):
    # Rank Math's title and description, as the live page printed them.
    head = get(f"http://localhost:4321/location/{slug}/").decode("utf-8", "replace").split("</head>")[0]
    title = re.search(r"<title>(.*?)</title>", head, re.S)
    desc = re.search(r'<meta name="description" content="([^"]*)"', head)
    # WordPress has no site name set, so its titles end in a bare " -".
    return (html.unescape(title.group(1)).strip().removesuffix(" -") if title else None, html.unescape(desc.group(1)).strip() if desc else None)


posts = json.loads(get(f"{WP}/wp/v2/posts?per_page=100&_embed=wp:featuredmedia"))
lines = []
for p in posts:
    slug = p["slug"]
    parsed = Blocks()
    parsed.feed(p["content"]["rendered"])
    parsed.close_block()
    featured = (p.get("_embedded", {}).get("wp:featuredmedia") or [{}])[0]
    main = {"src": featured["source_url"], "alt": featured.get("alt_text", "")} if featured.get("source_url") else (parsed.images[:1] or [None])[0]
    skipped = [i for i in parsed.images if i is not main]
    title = html.unescape(p["title"]["rendered"]).strip()
    excerpt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p["excerpt"]["rendered"]))).replace("[…]", "").replace("[&hellip;]", "").strip()
    if len(excerpt) > 200:
        excerpt = excerpt[:197].rsplit(" ", 1)[0] + "..."
    seo_title, seo_desc = seo(slug)
    doc = {
        "_id": f"drafts.loc-{slug}",
        "_type": "post",
        "title": title,
        "slug": {"_type": "slug", "current": slug},
        "excerpt": excerpt,
        "author": "SipLink Team",
        "publishedAt": p["date"][:10],
        "body": parsed.blocks,
    }
    if p["modified"][:10] > p["date"][:10]:
        doc["updatedAt"] = p["modified"][:10]
    if seo_title:
        doc["seoTitle"] = seo_title
    if seo_desc:
        doc["seoDescription"] = seo_desc
    if main:
        path = save_image(main["src"], slug)
        doc["mainImage"] = {"_type": "image", "alt": main["alt"] or title, "_sanityAsset": f"image@{path.resolve().as_uri()}"}
    lines.append(json.dumps(doc, ensure_ascii=False))
    print(f"{slug[:38]:40} blocks {len(parsed.blocks):3}  image {'yes' if main else 'NO '}  skipped imgs {len(skipped)}  seo {'yes' if seo_title else 'no'}")

(HERE / "location-posts.ndjson").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} drafts written")
