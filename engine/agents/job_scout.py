import re
import logging
from typing import List, Dict, Any, Optional, Set
import requests
from bs4 import BeautifulSoup
from engine.agents.base import BaseAgent
from engine.state import JobLead
from engine.tools.date_utils import parse_date_to_timestamp
from engine.tools.profile_matcher import is_profile_aligned
from engine.tools.location_matcher import get_india_remote_priority, is_india_remote_eligible

logger = logging.getLogger("JobScoutAgent")

class JobScoutAgent(BaseAgent):
    """
    Autonomous Scout specializing in fetching and validating remote engineering jobs.
    Gathers postings across multiple public APIs, filters for role alignment at source,
    and sorts candidates newest-first.
    """

    def __init__(self):
        super().__init__(name="JobScoutAgent", role="Targeted Remote Job Sourcing Specialist")

    def run(self, limit: int = 40, seen_companies: Optional[Any] = None, page_offset: int = 0) -> List[JobLead]:
        leads: List[JobLead] = []
        seen = set(seen_companies or set())
        collected_companies = set()

        def add_leads(new_leads: List[JobLead]):
            for l in new_leads:
                ck = l.company.strip().lower()
                if ck not in seen and ck not in collected_companies:
                    leads.append(l)
                    collected_companies.add(ck)

        per_source = max(15, limit // 3)

        # Source 1: RemoteOK (AI, Python, Backend, Data, Cloud)
        try:
            add_leads(self._fetch_remoteok(limit=per_source, seen=seen))
        except Exception as e:
            logger.error(f"RemoteOK fetch failed: {e}")

        # Source 2: Remotive (AI, LLM, Agent, Machine Learning, Python, Backend)
        try:
            add_leads(self._fetch_remotive(limit=per_source, seen=seen))
        except Exception as e:
            logger.error(f"Remotive fetch failed: {e}")

        # Source 3: Jobicy (Python, Data-Science, Engineering, Backend)
        try:
            add_leads(self._fetch_jobicy(limit=per_source, seen=seen))
        except Exception as e:
            logger.error(f"Jobicy fetch failed: {e}")

        # Source 4: HN Who is Hiring (Monthly YC/HN Remote hiring thread)
        try:
            add_leads(self._fetch_hn_who_is_hiring(limit=per_source, seen=seen))
        except Exception as e:
            logger.error(f"HN Who is Hiring fetch failed: {e}")

        # Source 5: Arbeitnow (Multi-page global remote jobs)
        if len(leads) < limit:
            try:
                add_leads(self._fetch_arbeitnow(limit=limit - len(leads), seen=seen, page_offset=page_offset))
            except Exception as e:
                logger.error(f"Arbeitnow fetch failed: {e}")

        # Sort all aggregated candidate leads: India Remote & Worldwide first, then newest first
        leads.sort(
            key=lambda x: (get_india_remote_priority(x.location, x.description)[0], x.timestamp),
            reverse=True
        )
        return leads[:limit]

    def _fetch_remoteok(self, limit: int = 25, seen: Optional[Any] = None) -> List[JobLead]:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        target_tags = ["ai", "python", "machine-learning", "backend", "data", "cloud", "apac"]
        seen_set = set(seen or set())

        raw_candidates = []
        for tag in target_tags:
            try:
                url = f"https://remoteok.com/api?tag={tag}"
                res = requests.get(url, headers=headers, timeout=8)
                if res.status_code == 200:
                    for item in res.json():
                        if isinstance(item, dict) and item.get("position"):
                            raw_candidates.append(item)
            except Exception:
                continue

        raw_candidates.sort(key=lambda x: parse_date_to_timestamp(x.get("epoch") or x.get("date")), reverse=True)

        leads: List[JobLead] = []
        collected = set()

        for item in raw_candidates:
            title = item.get("position", "").strip()
            company = item.get("company", "").strip()
            ck = company.lower()
            if not company or ck in seen_set or ck in collected:
                continue

            desc_html = item.get("description", "")
            desc_clean = BeautifulSoup(desc_html, "html.parser").get_text()[:3000]
            tags = item.get("tags", [])

            aligned, _ = is_profile_aligned(title=title, description=desc_clean, tags=tags)
            if not aligned:
                continue

            domain_guess = re.sub(r'[^a-zA-Z0-9]', '', company).lower() + ".com"
            pub_date = item.get("date") or ""
            ts = parse_date_to_timestamp(item.get("epoch") or pub_date)

            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")
            salary_str = f"${salary_min:,} - ${salary_max:,}" if salary_min and salary_max else None

            lead = JobLead(
                company=company,
                domain=domain_guess,
                role=title,
                source_channel="RemoteOK",
                is_remote=True,
                location=item.get("location") or "Worldwide / Remote",
                url=item.get("url") or item.get("apply_url") or "",
                description=desc_clean,
                salary_raw=salary_str,
                published_at=pub_date,
                timestamp=ts
            )
            leads.append(lead)
            collected.add(ck)
            if len(leads) >= limit:
                break

        return leads

    def _fetch_remotive(self, limit: int = 25, seen: Optional[Any] = None) -> List[JobLead]:
        search_terms = ["ai", "llm", "agent", "machine learning", "python", "data engineer", "backend"]
        seen_set = set(seen or set())
        raw_items = []

        for term in search_terms:
            try:
                url = f"https://remotive.com/api/remote-jobs?search={term}"
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                if res.status_code == 200:
                    raw_items.extend(res.json().get("jobs", []))
            except Exception:
                continue

        raw_items.sort(key=lambda x: parse_date_to_timestamp(x.get("publication_date")), reverse=True)

        leads: List[JobLead] = []
        collected = set()

        for item in raw_items:
            title = item.get("title", "").strip()
            company = item.get("company_name", "").strip()
            ck = company.lower()
            if not company or ck in seen_set or ck in collected:
                continue

            desc_clean = BeautifulSoup(item.get("description", ""), "html.parser").get_text()[:3000]
            tags = item.get("tags", [])

            aligned, _ = is_profile_aligned(title=title, description=desc_clean, tags=tags)
            if not aligned:
                continue

            domain_guess = re.sub(r'[^a-zA-Z0-9]', '', company).lower() + ".com"
            pub_date = item.get("publication_date", "")
            ts = parse_date_to_timestamp(pub_date)

            lead = JobLead(
                company=company,
                domain=domain_guess,
                role=title,
                source_channel="Remotive Remote API",
                is_remote=True,
                location=item.get("candidate_required_location") or "Worldwide",
                url=item.get("url", ""),
                description=desc_clean,
                salary_raw=item.get("salary") or None,
                published_at=pub_date,
                timestamp=ts
            )
            leads.append(lead)
            collected.add(ck)
            if len(leads) >= limit:
                break

        return leads

    def _fetch_jobicy(self, limit: int = 25, seen: Optional[Any] = None) -> List[JobLead]:
        tags = ["python", "data-science", "engineering", "backend"]
        seen_set = set(seen or set())
        raw_items = []

        for tag in tags:
            try:
                url = f"https://jobicy.com/api/v2/remote-jobs?count=50&tag={tag}"
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                if res.status_code == 200:
                    raw_items.extend(res.json().get("jobs", []))
            except Exception:
                continue

        raw_items.sort(key=lambda x: parse_date_to_timestamp(x.get("pubDate")), reverse=True)

        leads: List[JobLead] = []
        collected = set()

        for item in raw_items:
            title = item.get("jobTitle", "").strip()
            company = item.get("companyName", "").strip()
            ck = company.lower()
            if not company or ck in seen_set or ck in collected:
                continue

            desc_clean = BeautifulSoup(item.get("jobDescription", ""), "html.parser").get_text()[:3000]

            aligned, _ = is_profile_aligned(title=title, description=desc_clean)
            if not aligned:
                continue

            domain_guess = re.sub(r'[^a-zA-Z0-9]', '', company).lower() + ".com"
            s_min = item.get("salaryMin")
            s_max = item.get("salaryMax")
            curr = item.get("salaryCurrency", "USD")
            salary_str = f"{s_min} - {s_max} {curr}" if s_min and s_max else None

            pub_date = item.get("pubDate", "")
            ts = parse_date_to_timestamp(pub_date)

            lead = JobLead(
                company=company,
                domain=domain_guess,
                role=title,
                source_channel="Jobicy Remote API",
                is_remote=True,
                location=item.get("jobGeo") or "Remote",
                url=item.get("url", ""),
                description=desc_clean,
                salary_raw=salary_str,
                published_at=pub_date,
                timestamp=ts
            )
            leads.append(lead)
            collected.add(ck)
            if len(leads) >= limit:
                break

        return leads

    def _fetch_hn_who_is_hiring(self, limit: int = 25, seen: Optional[Any] = None) -> List[JobLead]:
        seen_set = set(seen or set())
        try:
            story_res = requests.get(
                'https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query=hiring&hitsPerPage=1',
                timeout=8
            ).json()
            hits = story_res.get("hits", [])
            if not hits:
                return []

            story_id = hits[0].get("objectID")
            comments_res = requests.get(
                f'https://hn.algolia.com/api/v1/search_by_date?tags=comment,story_{story_id}&query=REMOTE&hitsPerPage=200',
                timeout=12
            ).json()
        except Exception:
            return []

        leads: List[JobLead] = []
        collected = set()

        for c in comments_res.get("hits", []):
            raw_text = BeautifulSoup(c.get("comment_text", ""), "html.parser").get_text()
            if not raw_text or "REMOTE" not in raw_text.upper():
                continue

            lines = raw_text.strip().split("\n")
            first_line = lines[0] if lines else ""
            parts = [p.strip() for p in first_line.split("|")]

            if len(parts) >= 2:
                company_name = parts[0]
                role = parts[1]
            else:
                company_name = first_line[:40].strip()
                role = "Software Engineer"

            company_clean = re.sub(r'[\(\[\{].*?[\)\]\}]', '', company_name).strip()
            ck = company_clean.lower()
            if not company_clean or len(company_clean) < 2 or len(company_clean) > 40 or ck in seen_set or ck in collected:
                continue

            aligned, _ = is_profile_aligned(title=role, description=raw_text)
            if not aligned:
                continue

            domain_guess = re.sub(r'[^a-zA-Z0-9]', '', company_clean).lower() + ".com"
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', raw_text)
            hint_email = emails[0] if emails else None
            ts = float(c.get("created_at_i") or parse_date_to_timestamp(c.get("created_at")))

            lead = JobLead(
                company=company_clean,
                domain=domain_guess,
                role=role,
                source_channel="HN Who is Hiring",
                is_remote=True,
                location="Remote",
                url=f"https://news.ycombinator.com/item?id={c.get('objectID')}",
                description=raw_text[:3000],
                direct_email_hint=hint_email,
                published_at=c.get("created_at"),
                timestamp=ts
            )
            leads.append(lead)
            collected.add(ck)
            if len(leads) >= limit:
                break

        return leads

    def _fetch_arbeitnow(self, limit: int = 30, seen: Optional[Any] = None, page_offset: int = 0) -> List[JobLead]:
        seen_set = set(seen or set())
        leads: List[JobLead] = []
        collected = set()

        for page in range(1 + page_offset, 4 + page_offset):
            try:
                res = requests.get(f"https://www.arbeitnow.com/api/job-board-api?page={page}", timeout=8).json()
                for job in res.get("data", []):
                    title = job.get("title", "")
                    company = job.get("company_name", "").strip()
                    ck = company.lower()
                    if not company or ck in seen_set or ck in collected:
                        continue

                    desc_text = BeautifulSoup(job.get("description", ""), "html.parser").get_text()

                    aligned, _ = is_profile_aligned(title=title, description=desc_text)
                    if not aligned:
                        continue

                    domain_guess = re.sub(r'[^a-zA-Z0-9]', '', company).lower() + ".com"
                    created_at = job.get("created_at")
                    ts = parse_date_to_timestamp(created_at)

                    lead = JobLead(
                        company=company,
                        domain=domain_guess,
                        role=title,
                        source_channel="Arbeitnow Remote API",
                        is_remote=job.get("remote", True),
                        location=job.get("location") or "Remote",
                        url=job.get("url", ""),
                        description=desc_text[:3000],
                        published_at=str(created_at),
                        timestamp=ts
                    )
                    leads.append(lead)
                    collected.add(ck)
                    if len(leads) >= limit:
                        return leads
            except Exception:
                continue

        return leads
