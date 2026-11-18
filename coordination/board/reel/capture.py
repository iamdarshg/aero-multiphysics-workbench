#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Instagram reel content capture.

Strategy (in the order the task asked for):
  1. og:description / og:title meta tags
  2. JSON-LD blocks (script[type="application/ld+json"])
  3. <video> element attributes + aria-labels
  4. Page text content / caption-like blocks
  5. Login-wall detection -> report plainly, do not fight it

Runs each pass twice: headless first, then visible (headed) Chromium.
Also dumps raw HTML + screenshots so a human can audit the claim later.

Usage:
    python capture.py
"""

import json
import re
import sys
import pathlib
import traceback

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------- config

URL = "https://www.instagram.com/reel/DfOLEP6v3AR/?srtk=MTlodmt1NmNxdmdyYg=="
SHORTCODE = "DfOLEP6v3AR"
EMBED_URL = "https://www.instagram.com/reel/%s/embed/captioned/" % SHORTCODE

OUT = pathlib.Path(__file__).resolve().parent

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

LOGIN_WALL_MARKERS = [
    "log in to continue",
    "log in to instagram",
    "you must log in",
    "sign up for instagram",
    "please log in",
    "login_form",
    "accounts/login",
]

# ---------------------------------------------------------------- helpers


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s)[:80]


def text_of(el_html):
    return el_html


def collect_meta(page):
    """Pass 1: og:/twitter:/description meta tags."""
    js = r"""
    () => {
      const out = {};
      for (const m of document.querySelectorAll('meta')) {
        const k = m.getAttribute('property') || m.getAttribute('name') || '';
        const v = m.getAttribute('content') || '';
        if (!k) continue;
        if (/^(og:|twitter:|description$|title$|al:)/i.test(k)) out[k] = v;
      }
      return {
        meta: out,
        docTitle: document.title,
        canonical: (document.querySelector('link[rel=canonical]') || {}).href || null,
      };
    }
    """
    try:
        return page.evaluate(js)
    except Exception as e:
        return {"meta": {}, "docTitle": None, "canonical": None, "error": repr(e)}


def collect_jsonld(page):
    """Pass 2: JSON-LD blocks, parsed where possible."""
    js = r"""
    () => {
      const blocks = [];
      for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
        blocks.push(s.textContent);
      }
      return blocks;
    }
    """
    try:
        raw = page.evaluate(js)
    except Exception as e:
        return {"raw": [], "parsed": [], "error": repr(e)}

    parsed = []
    for b in raw:
        if not b:
            continue
        try:
            parsed.append(json.loads(b))
        except Exception:
            parsed.append({"__unparsed__": b[:2000]})
    return {"raw": raw, "parsed": parsed}


def collect_media(page):
    """Pass 3: <video>/<audio> attributes, aria-labels, img alts."""
    js = r"""
    () => {
      const vids = [...document.querySelectorAll('video, audio')].map(v => ({
        tag: v.tagName,
        src: v.getAttribute('src') || v.currentSrc || null,
        poster: v.getAttribute('poster') || null,
        duration: v.duration ?? null,
        width: v.getAttribute('width'),
        height: v.getAttribute('height'),
        ariaLabel: v.getAttribute('aria-label'),
        attrs: Object.fromEntries([...v.attributes].map(a => [a.name, a.value]))
      }));
      const labels = [...document.querySelectorAll('[aria-label]')]
        .map(e => ({ tag: e.tagName, label: e.getAttribute('aria-label') }))
        .filter(x => x.label && x.label.trim().length > 2)
        .slice(0, 200);
      const imgs = [...document.querySelectorAll('img')]
        .map(i => ({ alt: i.getAttribute('alt'), src: i.currentSrc || i.src || null }))
        .slice(0, 100);
      return { media: vids, ariaLabels: labels, images: imgs };
    }
    """
    try:
        return page.evaluate(js)
    except Exception as e:
        return {"media": [], "ariaLabels": [], "images": [], "error": repr(e)}


def collect_page_text(page):
    """Pass 4: innerText plus candidate caption blocks."""
    js = r"""
    () => {
      const bodyText = document.body ? document.body.innerText : '';
      // Instagram marks the caption with a span/h1 often inside an <article>.
      const cands = [];
      const sels = ['h1', 'article h1', 'article span', 'meta[property="og:description"]'];
      for (const sel of sels) {
        for (const e of document.querySelectorAll(sel)) {
          const t = (e.innerText || e.textContent || '').trim();
          if (t.length > 40 && t.length < 5000) {
            cands.push({ sel, text: t });
          }
        }
      }
      // de-dup, keep longest few
      const seen = new Set();
      const uniq = [];
      for (const c of cands) {
        if (seen.has(c.text)) continue;
        seen.add(c.text);
        uniq.push(c);
      }
      uniq.sort((a, b) => b.text.length - a.text.length);
      return { bodyText, candidates: uniq.slice(0, 25), bodyLen: bodyText.length };
    }
    """
    try:
        return page.evaluate(js)
    except Exception as e:
        return {"bodyText": "", "candidates": [], "bodyLen": 0, "error": repr(e)}


def detect_login_wall(page):
    js = r"""
    () => {
      const t = (document.body ? document.body.innerText : '').toLowerCase();
      const hasPw = !!document.querySelector('input[type="password"]');
      const loginLinks = [...document.querySelectorAll('a')]
        .map(a => a.getAttribute('href') || '')
        .filter(h => h.includes('/accounts/login'));
      return { hasPasswordInput: hasPw, loginLinkCount: loginLinks.length, textHead: t.slice(0, 600) };
    }
    """
    try:
        info = page.evaluate(js)
    except Exception as e:
        return {"error": repr(e), "wall": False}

    hay = (info.get("textHead") or "") + " "
    hits = [m for m in LOGIN_WALL_MARKERS if m in hay]
    info["markerHits"] = hits
    info["wall"] = bool(info.get("hasPasswordInput") or info.get("loginLinkCount", 0) > 0 or hits)
    return info


def run_pass(pw, label, headless, url, wait_ms=6000):
    """One full extraction pass against a URL."""
    print("\n=== PASS %s (headless=%s) :: %s ===" % (label, headless, url), flush=True)
    result = {"pass": label, "headless": headless, "url": url}
    browser = pw.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1400, "height": 1000},
        locale="en-US",
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    page = ctx.new_page()
    nav = {"status": None, "error": None}
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        nav["status"] = resp.status if resp else None
    except Exception as e:
        nav["error"] = repr(e)
    result["navigation"] = nav

    try:
        page.wait_for_timeout(wait_ms)
    except Exception:
        pass

    result["loginWall"] = detect_login_wall(page)
    result["meta"] = collect_meta(page)
    result["jsonld"] = collect_jsonld(page)
    result["mediaBlock"] = collect_media(page)
    result["pageText"] = collect_page_text(page)

    # artifacts
    stem = "%s-%s" % (label, "headless" if headless else "headed")
    try:
        (OUT / ("page-%s.html" % stem)).write_text(page.content(), encoding="utf-8")
    except Exception as e:
        result["htmlDumpError"] = repr(e)
    try:
        page.screenshot(path=str(OUT / ("shot-%s.png" % stem)), full_page=False)
    except Exception as e:
        result["screenshotError"] = repr(e)

    ctx.close()
    browser.close()
    return result


def try_embed(pw):
    """Extra: the /embed/captioned/ endpoint frequently serves the caption
    without a login wall. Documented as a supplementary probe."""
    print("\n=== PASS embed (headless=True) :: %s ===" % EMBED_URL, flush=True)
    result = {"pass": "embed", "url": EMBED_URL}
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent=USER_AGENT, locale="en-US")
    page = ctx.new_page()
    try:
        resp = page.goto(EMBED_URL, wait_until="domcontentloaded", timeout=60000)
        result["status"] = resp.status if resp else None
        page.wait_for_timeout(5000)
        result["bodyText"] = page.evaluate("() => document.body ? document.body.innerText : ''")
        result["html"] = page.content()[:400000]
        page.screenshot(path=str(OUT / "shot-embed.png"), full_page=True)
    except Exception as e:
        result["error"] = repr(e)
    finally:
        ctx.close()
        browser.close()
    return result


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    results = {"url": URL, "shortcode": SHORTCODE, "passes": []}
    with sync_playwright() as pw:
        for label, headless in (("live", True), ("live", False)):
            try:
                results["passes"].append(run_pass(pw, label, headless, URL))
            except Exception:
                results["passes"].append({"pass": label, "headless": headless,
                                          "fatal": traceback.format_exc()})
        try:
            results["embed"] = try_embed(pw)
        except Exception:
            results["embed"] = {"fatal": traceback.format_exc()}

    # strip the huge embed html from the json we print, keep it on disk
    embed_html = results.get("embed", {}).pop("html", None)
    if embed_html:
        (OUT / "page-embed.html").write_text(embed_html, encoding="utf-8")

    (OUT / "raw-results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ---- console summary
    print("\n\n########## SUMMARY ##########")
    for p in results["passes"]:
        print("\n-- %s headless=%s status=%s" % (
            p.get("pass"), p.get("headless"), (p.get("navigation") or {}).get("status")))
        m = (p.get("meta") or {}).get("meta") or {}
        print("   docTitle : %r" % ((p.get("meta") or {}).get("docTitle"),))
        print("   og:title : %r" % (m.get("og:title"),))
        print("   og:desc  : %r" % (m.get("og:description"),))
        print("   loginWall: %r" % (p.get("loginWall"),))
        jl = p.get("jsonld") or {}
        print("   jsonld blocks: %d" % len(jl.get("raw") or []))
        print("   media count: %d" % len(((p.get("mediaBlock") or {}).get("media")) or []))
        print("   bodyLen: %s" % ((p.get("pageText") or {}).get("bodyLen")))
        pt = p.get("pageText") or {}
        print("   bodyText head:\n%s" % (pt.get("bodyText", "")[:1500]))
        for c in (pt.get("candidates") or [])[:5]:
            print("   [cand %s] %r" % (c.get("sel"), c.get("text")[:600]))

    e = results.get("embed") or {}
    print("\n-- embed status=%s" % e.get("status"))
    print("   bodyText:\n%s" % (e.get("bodyText", "")[:2000]))

    print("\nWrote: raw-results.json, page-*.html, shot-*.png in %s" % OUT)


if __name__ == "__main__":
    main()