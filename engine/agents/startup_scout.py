import os
import re
import json
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from engine.agents.base import BaseAgent
from engine.state import JobLead
from engine.config import TARGET_STARTUPS_PATH
from engine.tools.date_utils import parse_date_to_timestamp

logger = logging.getLogger("FundedStartupAgent")

def clean_domain_from_url(url: str, fallback_name: str) -> str:
    """Extracts a clean root domain from a website URL, falling back to slug.com."""
    if url:
        try:
            parsed = urllib.parse.urlparse(url)
            netloc = re.sub(r'^www\.', '', parsed.netloc or parsed.path).split(':')[0]
            if netloc and '.' in netloc and not any(d in netloc.lower() for d in [
                'github.com', 'ycombinator.com', 'goodfirstissue.dev',
                'up-for-grabs.net', 'ossean.com', 'opensourcestartups.com',
                'unicornscreener.vc'
            ]):
                return netloc
        except Exception:
            pass
    clean = re.sub(r'[^a-zA-Z0-9]', '', fallback_name).lower()
    return f"{clean}.com" if clean else "startup.com"


class FundedStartupAgent(BaseAgent):
    """
    Autonomous Scout discovering high-potential AI, developer infrastructure,
    open-source startups, and newly funded engineering ventures across 8 specialized sources:
    1. YC Open Source Companies (yc-oss)
    2. Unicorn Screener OSS Radar
    3. OSSEAN AI Apps & Autonomous Agents
    4. OpenSourceStartups directory
    5. GitHub Trending (Python, TypeScript, Overall) & Explore
    6. GoodFirstIssue & Up-For-Grabs (Active contributor-seeking open-source projects)
    7. TechCrunch AI & Enterprise Funding RSS
    8. Hacker News AI Funding & Launch HN stories
    """

    def __init__(self):
        super().__init__(name="FundedStartupAgent", role="AI Venture Capital & Startup Scout")

    def run(self, limit: int = 30, seen_companies: Optional[Any] = None, page_offset: int = 0) -> List[JobLead]:
        seen = set(seen_companies or set())
        collected = set()
        bucket_limit = max(6, limit // 3)

        # 1. Open Source Startups (YC OSS, Unicorn Screener, OSSEAN, OpenSourceStartups, GitHub Trending, GoodFirstIssue, Up-For-Grabs)
        oss_leads: List[JobLead] = []
        for fetcher in [
            lambda: self._fetch_yc_oss_companies(limit=bucket_limit, seen=seen),
            lambda: self._fetch_unicornscreener_radar(limit=bucket_limit, seen=seen),
            lambda: self._fetch_ossean_and_opensource_startups(limit=bucket_limit, seen=seen),
            lambda: self._fetch_github_trending_and_explore(limit=bucket_limit, seen=seen),
            lambda: self._fetch_contributor_seeking_oss(limit=bucket_limit, seen=seen),
        ]:
            try:
                for l in fetcher():
                    ck = l.company.strip().lower()
                    if ck not in seen and ck not in collected:
                        oss_leads.append(l)
                        collected.add(ck)
            except Exception as e:
                logger.warning(f"OSS scout fetch failed: {e}")

        # 2. Funded AI Ventures & Launches (TechCrunch AI, HN AI Funding, Launch HN)
        funded_leads: List[JobLead] = []
        for fetcher in [
            lambda: self._fetch_techcrunch_ai_funding(limit=bucket_limit, seen=seen),
            lambda: self._fetch_hn_ai_funding_and_launches(limit=bucket_limit, seen=seen),
        ]:
            try:
                for l in fetcher():
                    ck = l.company.strip().lower()
                    if ck not in seen and ck not in collected:
                        funded_leads.append(l)
                        collected.add(ck)
            except Exception as e:
                logger.warning(f"Funded scout fetch failed: {e}")

        # 3. Curated Target Startups (Langfuse, Portkey, Modal, Fireworks, etc.)
        curated_leads: List[JobLead] = []
        try:
            for l in self._fetch_curated_startups(limit=bucket_limit, seen=seen):
                ck = l.company.strip().lower()
                if ck not in seen and ck not in collected:
                    curated_leads.append(l)
                    collected.add(ck)
        except Exception as e:
            logger.warning(f"Curated scout fetch failed: {e}")

        # Interleave across OSS startups, newly funded AI ventures, and curated targets
        combined: List[JobLead] = []
        max_ct = max(len(oss_leads), len(funded_leads), len(curated_leads), 1)
        for i in range(max_ct):
            if i < len(oss_leads):
                combined.append(oss_leads[i])
            if i < len(funded_leads):
                combined.append(funded_leads[i])
            if i < len(curated_leads):
                combined.append(curated_leads[i])

        return combined[:limit]

    def _fetch_yc_oss_companies(self, limit: int = 15, seen: Optional[Any] = None) -> List[JobLead]:
        """Fetches commercial open-source startups funded by Y Combinator."""
        seen_set = set(seen or set())
        leads: List[JobLead] = []
        collected = set()

        # Primary: YC OSS API
        try:
            res = requests.get(
                "https://yc-oss.github.io/api/tags/open-source.json",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            if res.status_code == 200:
                items = res.json()
                for it in items:
                    name = it.get("name", "").strip()
                    ck = name.lower()
                    if not name or len(name) < 2 or ck in seen_set or ck in collected:
                        continue
                    website = it.get("website") or it.get("url") or ""
                    dom = clean_domain_from_url(website, name)
                    batch = it.get("batch") or "OSS"
                    desc = it.get("long_description") or it.get("one_liner") or f"{name} is an open source company funded by Y Combinator."
                    leads.append(JobLead(
                        company=name,
                        domain=dom,
                        role="Founding AI / Systems Engineer (Proactive Outreach)",
                        source_channel="YC Open Source",
                        is_remote=True,
                        location=it.get("all_locations") or "Remote / Global",
                        url=website or it.get("url", ""),
                        description=desc[:1500],
                        funding_info=f"Y Combinator ({batch})",
                        timestamp=float(it.get("launched_at") or 0.0)
                    ))
                    collected.add(ck)
                    if len(leads) >= limit:
                        return leads
        except Exception as e:
            logger.warning(f"YC OSS API fetch failed: {e}")

        # Fallback: YC OSS README Markdown table
        if len(leads) < limit:
            try:
                res_md = requests.get(
                    "https://raw.githubusercontent.com/yc-oss/open-source-companies/main/README.md",
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10
                )
                if res_md.status_code == 200:
                    for line in res_md.text.splitlines():
                        if "|" not in line or "Company" in line or "---" in line:
                            continue
                        parts = [p.strip() for p in line.split("|") if p.strip()]
                        if len(parts) >= 2:
                            name_match = re.search(r'\[([^\]]+)\]', parts[0])
                            name = name_match.group(1).strip() if name_match else parts[0].strip()
                            ck = name.lower()
                            if not name or len(name) < 2 or ck in seen_set or ck in collected:
                                continue
                            link_match = re.search(r'\((https?://[^\)]+)\)', parts[0])
                            website = link_match.group(1) if link_match else ""
                            batch = parts[1] if len(parts) > 1 else "OSS"
                            leads.append(JobLead(
                                company=name,
                                domain=clean_domain_from_url(website, name),
                                role="Founding AI / Systems Engineer (Proactive Outreach)",
                                source_channel="YC Open Source",
                                is_remote=True,
                                location="Remote / Global",
                                url=website or "https://github.com/yc-oss/open-source-companies",
                                description=f"{name} is a Y Combinator backed open-source startup ({batch}).",
                                funding_info=f"Y Combinator ({batch})",
                                timestamp=0.0
                            ))
                            collected.add(ck)
                            if len(leads) >= limit:
                                break
            except Exception as e:
                logger.error(f"YC OSS README fallback failed: {e}")

        return leads

    def _fetch_unicornscreener_radar(self, limit: int = 15, seen: Optional[Any] = None) -> List[JobLead]:
        """Fetches fast-growing open source repositories from Unicorn Screener OSS Radar."""
        seen_set = set(seen or set())
        leads: List[JobLead] = []
        collected = set()

        try:
            res = requests.get(
                "https://unicornscreener.vc/open-source-radar",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                links = soup.find_all("a", href=re.compile(r'https?://github\.com/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)'))
                for a in links:
                    m = re.match(r'https?://github\.com/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)', a['href'])
                    if not m:
                        continue
                    org, repo = m.group(1), m.group(2)
                    comp = repo.replace("-", " ").title()
                    ck = comp.lower()
                    if ck in seen_set or ck in collected or org.lower() in ["github", "yc-oss"]:
                        continue
                    row = a.find_parent("tr") or a.find_parent("div")
                    desc = row.get_text(" ", strip=True) if row else f"{comp} high-growth open source repository ({org}/{repo})."
                    leads.append(JobLead(
                        company=comp,
                        domain=clean_domain_from_url("", comp),
                        role="Founding AI / Systems Engineer (Proactive Outreach)",
                        source_channel="Unicorn Screener OSS",
                        is_remote=True,
                        location="Remote / Global",
                        url=f"https://github.com/{org}/{repo}",
                        description=desc[:1200],
                        funding_info="High-Growth Open Source (Unicorn Screener Radar)",
                        timestamp=0.0
                    ))
                    collected.add(ck)
                    if len(leads) >= limit:
                        break
        except Exception as e:
            logger.error(f"Unicorn Screener radar fetch failed: {e}")

        return leads

    def _fetch_github_trending_and_explore(self, limit: int = 20, seen: Optional[Any] = None) -> List[JobLead]:
        """Fetches weekly trending repositories in Python, TypeScript, and overall, plus GitHub Explore."""
        seen_set = set(seen or set())
        leads: List[JobLead] = []
        collected = set()

        trending_urls = [
            ("https://github.com/trending/python?since=weekly", "GitHub Trending (Python)"),
            ("https://github.com/trending?since=weekly", "GitHub Trending (Overall)"),
            ("https://github.com/trending/typescript?since=weekly", "GitHub Trending (TypeScript)"),
            ("https://github.com/explore", "GitHub Explore")
        ]

        for url, channel in trending_urls:
            if len(leads) >= limit:
                break
            try:
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                if res.status_code != 200:
                    continue
                soup = BeautifulSoup(res.text, "html.parser")
                if "trending" in url:
                    rows = soup.select("article.Box-row")
                    for row in rows:
                        h2 = row.select_one("h2 a")
                        if not h2:
                            continue
                        full_name = h2.get_text(strip=True).replace(" ", "").replace("\n", "")
                        parts = full_name.split("/")
                        if len(parts) != 2:
                            continue
                        repo = parts[1]
                        comp = repo.replace("-", " ").title()
                        ck = comp.lower()
                        if ck in seen_set or ck in collected or len(comp) < 2:
                            continue
                        p = row.select_one("p")
                        stars = row.select_one("a[href*='/stargazers']")
                        star_txt = stars.get_text(strip=True) if stars else "Trending"
                        desc = p.get_text(strip=True) if p else f"Trending GitHub repository {full_name} ({star_txt} stars)."
                        leads.append(JobLead(
                            company=comp,
                            domain=clean_domain_from_url("", comp),
                            role="Founding AI / Systems Engineer (Proactive Outreach)",
                            source_channel=channel,
                            is_remote=True,
                            location="Remote / Global",
                            url=f"https://github.com/{full_name}",
                            description=f"{desc} — Star count: {star_txt}",
                            funding_info=f"Trending Open Source ({star_txt} stars)",
                            timestamp=0.0
                        ))
                        collected.add(ck)
                        if len(leads) >= limit:
                            break
                else:
                    repos = set(re.findall(r'href=[\"\']/([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)[\"\']', res.text))
                    for slug in repos:
                        if any(slug.startswith(p) for p in ['topics/', 'collections/', 'site/', 'features/', 'events/', 'trending/']):
                            continue
                        parts = slug.split('/')
                        if len(parts) != 2:
                            continue
                        repo = parts[1]
                        comp = repo.replace("-", " ").title()
                        ck = comp.lower()
                        if ck in seen_set or ck in collected or len(comp) < 2:
                            continue
                        leads.append(JobLead(
                            company=comp,
                            domain=clean_domain_from_url("", comp),
                            role="Founding AI / Systems Engineer (Proactive Outreach)",
                            source_channel=channel,
                            is_remote=True,
                            location="Remote / Global",
                            url=f"https://github.com/{slug}",
                            description=f"Curated open source repository on GitHub Explore: {slug}",
                            funding_info="Curated GitHub Open Source",
                            timestamp=0.0
                        ))
                        collected.add(ck)
                        if len(leads) >= limit:
                            break
            except Exception as e:
                logger.warning(f"Failed fetching {channel} from {url}: {e}")

        return leads

    def _fetch_ossean_and_opensource_startups(self, limit: int = 20, seen: Optional[Any] = None) -> List[JobLead]:
        """Fetches active open-source AI apps from OSSEAN and curated startups from OpenSourceStartups."""
        seen_set = set(seen or set())
        leads: List[JobLead] = []
        collected = set()

        # 1. OSSEAN AI Apps & Autonomous Agents
        try:
            res = requests.get(
                "https://ossean.com/category/ai-apps-and-agents",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for a in soup.find_all("a", href=re.compile(r'^/[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+$')):
                    href = a['href']
                    if any(href.startswith(p) for p in ['/audience', '/alternatives', '/category', '/about', '/status']):
                        continue
                    txt = a.get_text(" ", strip=True)
                    parts = href.strip("/").split("/")
                    if len(parts) != 2:
                        continue
                    repo = parts[1]
                    comp = repo.replace("-", " ").title()
                    ck = comp.lower()
                    if ck in seen_set or ck in collected or len(comp) < 2:
                        continue
                    leads.append(JobLead(
                        company=comp,
                        domain=clean_domain_from_url("", comp),
                        role="Founding AI / Agent Systems Engineer (Proactive Outreach)",
                        source_channel="OSSEAN AI Apps",
                        is_remote=True,
                        location="Remote / Global",
                        url=f"https://ossean.com{href}",
                        description=txt or f"{comp} active open-source AI applications and autonomous agents project.",
                        funding_info="Commercial Open Source (OSSEAN Active Shipping)",
                        timestamp=0.0
                    ))
                    collected.add(ck)
                    if len(leads) >= limit // 2:
                        break
        except Exception as e:
            logger.warning(f"OSSEAN fetch failed: {e}")

        # 2. OpenSourceStartups directory
        try:
            res_oss = requests.get(
                "https://www.opensourcestartups.com/",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            if res_oss.status_code == 200:
                soup = BeautifulSoup(res_oss.text, "html.parser")
                for h3 in soup.find_all("h3"):
                    txt = h3.get_text(strip=True)
                    if not txt or len(txt) <= 2 or any(k in txt.lower() for k in ['free public', 'search', 'join', 'subscribe', 'fast']):
                        continue
                    ck = txt.lower()
                    if ck in seen_set or ck in collected:
                        continue
                    p = h3.find_next_sibling("p")
                    desc = p.get_text(strip=True) if p else f"{txt} commercial open-source startup."
                    slug = txt.lower().replace(" ", "-")
                    leads.append(JobLead(
                        company=txt,
                        domain=clean_domain_from_url("", txt),
                        role="Founding AI / Systems Engineer (Proactive Outreach)",
                        source_channel="OpenSourceStartups",
                        is_remote=True,
                        location="Remote / Global",
                        url=f"https://www.opensourcestartups.com/project/{slug}",
                        description=desc[:1200],
                        funding_info="Commercial Open Source Startup",
                        timestamp=0.0
                    ))
                    collected.add(ck)
                    if len(leads) >= limit:
                        break
        except Exception as e:
            logger.warning(f"OpenSourceStartups fetch failed: {e}")

        return leads

    def _fetch_contributor_seeking_oss(self, limit: int = 20, seen: Optional[Any] = None) -> List[JobLead]:
        """Fetches active open-source repositories from GoodFirstIssue and Up-For-Grabs."""
        seen_set = set(seen or set())
        leads: List[JobLead] = []
        collected = set()

        # 1. GoodFirstIssue (Python repositories)
        try:
            res = requests.get(
                "https://goodfirstissue.dev/language/python/",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            if res.status_code == 200:
                gh_repos = set(re.findall(r'https?://github\.com/([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)', res.text))
                for slug in gh_repos:
                    if slug in ['deepsourcelabs/good-first-issue']:
                        continue
                    parts = slug.split('/')
                    if len(parts) != 2:
                        continue
                    repo = parts[1]
                    comp = repo.replace("-", " ").title()
                    ck = comp.lower()
                    if ck in seen_set or ck in collected or len(comp) < 2:
                        continue
                    leads.append(JobLead(
                        company=comp,
                        domain=clean_domain_from_url("", comp),
                        role="Founding AI / Systems Engineer (Proactive Outreach)",
                        source_channel="GoodFirstIssue",
                        is_remote=True,
                        location="Remote / Global",
                        url=f"https://github.com/{slug}",
                        description=f"Active open source project {slug} actively seeking engineering contributors.",
                        funding_info="Active Open Source Project",
                        timestamp=0.0
                    ))
                    collected.add(ck)
                    if len(leads) >= limit // 2:
                        break
        except Exception as e:
            logger.warning(f"GoodFirstIssue fetch failed: {e}")

        # 2. Up-For-Grabs JSON API (Filtered for AI, ML, Data, Streaming, Agent tags)
        try:
            res_ufg = requests.get(
                "https://up-for-grabs.net/javascripts/projects.json",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            if res_ufg.status_code == 200:
                data = res_ufg.json()
                ai_tags = {'ai', 'python', 'machine-learning', 'agent', 'llm', 'data', 'streaming', 'rust', 'deep-learning'}
                for k, it in data.items():
                    tags = set(t.lower() for t in it.get("tags", []))
                    if not tags.intersection(ai_tags):
                        continue
                    comp = it.get("name", "").strip()
                    ck = comp.lower()
                    if not comp or len(comp) < 2 or ck in seen_set or ck in collected:
                        continue
                    site = it.get("site", "")
                    leads.append(JobLead(
                        company=comp,
                        domain=clean_domain_from_url(site, comp),
                        role="Founding AI / Systems Engineer (Proactive Outreach)",
                        source_channel="Up-For-Grabs",
                        is_remote=True,
                        location="Remote / Global",
                        url=site or it.get("upforgrabs", {}).get("link", f"https://up-for-grabs.net/#/{comp}"),
                        description=it.get("desc") or f"{comp} open-source contributor project.",
                        funding_info="Open Source Contributor Project",
                        timestamp=0.0
                    ))
                    collected.add(ck)
                    if len(leads) >= limit:
                        break
        except Exception as e:
            logger.warning(f"Up-For-Grabs fetch failed: {e}")

        return leads

    def _fetch_curated_startups(self, limit: int = 15, seen: Optional[Any] = None) -> List[JobLead]:
        if not TARGET_STARTUPS_PATH.exists():
            return []

        seen_set = set(seen or set())
        try:
            with open(TARGET_STARTUPS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []

        leads: List[JobLead] = []
        for item in data:
            comp = item.get("company", "").strip()
            ck = comp.lower()
            if not comp or ck in seen_set:
                continue

            lead = JobLead(
                company=comp,
                domain=item.get("domain", ""),
                role=item.get("role", "Founding AI Engineer"),
                source_channel="Curated AI Startup",
                is_remote=True,
                location="Remote",
                url=item.get("url", ""),
                description=item.get("description", ""),
                direct_email_hint=item.get("direct_email") or None,
                funding_info=item.get("funding_info", "VC-backed (Seed/Series A)"),
                timestamp=0.0
            )
            leads.append(lead)
            if len(leads) >= limit:
                break

        return leads

    def _fetch_techcrunch_ai_funding(self, limit: int = 20, seen: Optional[Any] = None) -> List[JobLead]:
        """Parses TechCrunch Artificial Intelligence & Enterprise RSS feeds."""
        seen_set = set(seen or set())
        rss_urls = [
            "https://techcrunch.com/category/artificial-intelligence/feed/",
            "https://techcrunch.com/category/enterprise/feed/",
            "https://techcrunch.com/category/startups/feed/"
        ]

        raw_articles = []
        for url in rss_urls:
            try:
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                if res.status_code == 200:
                    root = ET.fromstring(res.content)
                    for item in root.findall(".//item"):
                        title = item.find("title").text if item.find("title") is not None else ""
                        link = item.find("link").text if item.find("link") is not None else ""
                        desc = item.find("description").text if item.find("description") is not None else ""
                        pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                        desc_clean = BeautifulSoup(desc, "html.parser").get_text()[:400]

                        # Check for funding keywords
                        if any(w in title.lower() for w in ["raises", "seed", "series a", "series b", "million", "funding", "backed"]):
                            ts = parse_date_to_timestamp(pub_date)
                            raw_articles.append({
                                "title": title,
                                "url": link,
                                "desc": desc_clean,
                                "pub_date": pub_date,
                                "timestamp": ts
                            })
            except Exception as e:
                logger.warning(f"Failed parsing RSS {url}: {e}")

        # Sort newest first
        raw_articles.sort(key=lambda x: x["timestamp"], reverse=True)

        leads: List[JobLead] = []
        collected = set()
        for art in raw_articles:
            title = art["title"]

            # Fast deterministic regex parsing for headlines like "Mach9 raises $34M..."
            match = re.search(r'([A-Za-z0-9\s]+?)\s+(?:raises|scores|secures|bags|closes|lands)\s+(\$[\d\.]+[MBK]?|\d+\s*million|seed|series\s+[a-c])', title, re.IGNORECASE)
            if match:
                comp_raw = match.group(1).strip()
                funding = match.group(2).strip()
                clean_comp = re.sub(r'^(?:AI startup|Startup|Maker|Creator|App|Platform)\s+', '', comp_raw, flags=re.IGNORECASE).strip()
                ck = clean_comp.lower()
                if 2 < len(clean_comp) < 35 and ck not in seen_set and ck not in collected:
                    dom_guess = re.sub(r'[^a-zA-Z0-9]', '', clean_comp).lower() + ".com"
                    leads.append(JobLead(
                        company=clean_comp,
                        domain=dom_guess,
                        role="Founding AI / Data Systems Engineer",
                        source_channel="TechCrunch AI Funding",
                        is_remote=True,
                        location="Remote / US / Global",
                        url=art["url"],
                        description=art["desc"] or f"{clean_comp} recently raised {funding} in the AI space.",
                        funding_info=funding,
                        published_at=art["pub_date"],
                        timestamp=art["timestamp"]
                    ))
                    collected.add(ck)
                    if len(leads) >= limit:
                        return leads

        return leads

    def _fetch_hn_ai_funding_and_launches(self, limit: int = 25, seen: Optional[Any] = None) -> List[JobLead]:
        """Pulls newly funded AI companies and Launch HN AI/Data startups."""
        seen_set = set(seen or set())
        leads: List[JobLead] = []
        collected = set()

        # 1. HN Stories with AI funding queries
        funding_queries = ["raises AI", "seed round AI", "Series A AI"]
        for fq in funding_queries:
            if len(leads) >= limit:
                break
            try:
                res_funding = requests.get(
                    f'https://hn.algolia.com/api/v1/search_by_date?tags=story&query={fq}&hitsPerPage=30',
                    timeout=8
                ).json()
                for post in res_funding.get("hits", []):
                    title = post.get("title", "")
                    match = re.search(r'([A-Za-z0-9\s]+?)\s+(?:raises|scores|secures|bags|closes)\s+(\$[\d\.]+[MBK]?|\d+\s*million|seed|series\s+[a-c])', title, re.IGNORECASE)
                    if match:
                        comp_raw = match.group(1).strip()
                        funding = match.group(2).strip()
                        clean_comp = re.sub(r'^(?:AI startup|Startup|Show HN:\s*AI startup|Show HN:)\s+', '', comp_raw, flags=re.IGNORECASE).strip()
                        clean_comp = re.sub(r'[\(\[\{].*?[\)\]\}]', '', clean_comp).strip()
                        ck = clean_comp.lower()
                        if 2 < len(clean_comp) < 35 and ck not in seen_set and ck not in collected:
                            dom_guess = re.sub(r'[^a-zA-Z0-9]', '', clean_comp).lower() + ".com"
                            ts = float(post.get("created_at_i") or parse_date_to_timestamp(post.get("created_at")))
                            leads.append(JobLead(
                                company=clean_comp,
                                domain=dom_guess,
                                role="Founding AI / Data Systems Engineer",
                                source_channel="HN AI Funding Story",
                                is_remote=True,
                                location="Remote / US",
                                url=post.get("url") or f"https://news.ycombinator.com/item?id={post.get('objectID')}",
                                description=title,
                                funding_info=funding,
                                published_at=post.get("created_at"),
                                timestamp=ts
                            ))
                            collected.add(ck)
                            if len(leads) >= limit:
                                break
            except Exception as e:
                logger.error(f"HN AI funding search error for '{fq}': {e}")

        # 2. Launch HN posts filtered for AI, Data, Developer Tools
        try:
            res_launch = requests.get(
                'https://hn.algolia.com/api/v1/search_by_date?tags=story&query="Launch HN:"&hitsPerPage=50',
                timeout=8
            ).json()
            tech_tokens = ["ai", "llm", "agent", "data", "streaming", "kafka", "rag", "vector", "api", "infra", "model", "eval"]
            for post in res_launch.get("hits", []):
                title = post.get("title", "")
                if not title.startswith("Launch HN:"):
                    continue

                story_text = post.get("story_text") or ""
                desc_clean = BeautifulSoup(story_text, "html.parser").get_text()[:1800]
                combined = (title + " " + desc_clean).lower()

                # Filter strictly for AI/Data/Infrastructure startups
                if not any(token in combined for token in tech_tokens):
                    continue

                company_match = re.search(r'Launch HN:\s*([^\(]+)', title)
                company_name = company_match.group(1).strip() if company_match else title.replace("Launch HN:", "").strip()
                company_name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', company_name).strip()
                ck = company_name.lower()
                if not company_name or len(company_name) < 2 or len(company_name) > 35 or ck in seen_set or ck in collected:
                    continue

                domain_guess = re.sub(r'[^a-zA-Z0-9]', '', company_name).lower() + ".com"
                ts = float(post.get("created_at_i") or parse_date_to_timestamp(post.get("created_at")))

                lead = JobLead(
                    company=company_name,
                    domain=domain_guess,
                    role="Founding AI / Agent Systems Engineer",
                    source_channel="Launch HN (AI/Data)",
                    is_remote=True,
                    location="Remote / US",
                    url=post.get("url") or f"https://news.ycombinator.com/item?id={post.get('objectID')}",
                    description=desc_clean or f"YC Startup {company_name} launching AI/Data platform on Hacker News.",
                    funding_info="Y Combinator / Venture Backed",
                    published_at=post.get("created_at"),
                    timestamp=ts
                )
                leads.append(lead)
                collected.add(ck)
                if len(leads) >= limit:
                    break
        except Exception as e:
            logger.error(f"Launch HN AI fetch error: {e}")

        return leads
