import os
import re
import json
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from engine.agents.base import BaseAgent
from engine.state import JobLead
from engine.config import TARGET_STARTUPS_PATH
from engine.tools.date_utils import parse_date_to_timestamp

logger = logging.getLogger("FundedStartupAgent")

class FundedStartupAgent(BaseAgent):
    """
    Autonomous Scout discovering newly funded AI, developer tools, and infrastructure startups.
    Pulls live RSS venture streams, Hacker News funding announcements, and curated target startups.
    """

    def __init__(self):
        super().__init__(name="FundedStartupAgent", role="AI Venture Capital & Startup Scout")

    def run(self, limit: int = 30, seen_companies: Optional[Any] = None, page_offset: int = 0) -> List[JobLead]:
        leads: List[JobLead] = []
        seen = set(seen_companies or set())
        collected = set()

        def add_leads(new_leads: List[JobLead]):
            for l in new_leads:
                ck = l.company.strip().lower()
                if ck not in seen and ck not in collected:
                    leads.append(l)
                    collected.add(ck)

        per_source_limit = max(10, limit // 2)

        # 1. TechCrunch AI, Enterprise & Startups RSS
        try:
            add_leads(self._fetch_techcrunch_ai_funding(limit=per_source_limit, seen=seen))
        except Exception as e:
            logger.error(f"TechCrunch AI funding fetch failed: {e}")

        # 2. Hacker News Targeted AI Funding Stories & Launch HN
        try:
            add_leads(self._fetch_hn_ai_funding_and_launches(limit=per_source_limit, seen=seen))
        except Exception as e:
            logger.error(f"HN AI funding & launches fetch failed: {e}")

        # 3. Curated Target Startups
        if len(leads) < limit:
            try:
                add_leads(self._fetch_curated_startups(limit=limit - len(leads), seen=seen))
            except Exception as e:
                logger.error(f"Curated startups fetch failed: {e}")

        leads.sort(key=lambda x: x.timestamp, reverse=True)
        return leads[:limit]

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
                role=item.get("role", "Founding Engineer"),
                source_channel="Target Startup Directory",
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

        raw_articles.sort(key=lambda x: x["timestamp"], reverse=True)

        leads: List[JobLead] = []
        collected = set()
        for art in raw_articles:
            title = art["title"]
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
                        role="Founding Systems / AI Engineer",
                        source_channel="TechCrunch Venture Funding",
                        is_remote=True,
                        location="Remote / US / Global",
                        url=art["url"],
                        description=art["desc"] or f"{clean_comp} recently raised {funding}.",
                        funding_info=funding,
                        published_at=art["pub_date"],
                        timestamp=art["timestamp"]
                    ))
                    collected.add(ck)
                    if len(leads) >= limit:
                        return leads

        return leads

    def _fetch_hn_ai_funding_and_launches(self, limit: int = 25, seen: Optional[Any] = None) -> List[JobLead]:
        seen_set = set(seen or set())
        leads: List[JobLead] = []
        collected = set()

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
                                role="Founding Engineer",
                                source_channel="HN Venture Funding",
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

        # Launch HN posts filtered for AI and Developer Tools
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
                    role="Founding Systems / AI Engineer",
                    source_channel="Launch HN",
                    is_remote=True,
                    location="Remote / US",
                    url=post.get("url") or f"https://news.ycombinator.com/item?id={post.get('objectID')}",
                    description=desc_clean or f"YC Startup {company_name} launching on Hacker News.",
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
