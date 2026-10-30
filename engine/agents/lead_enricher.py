import re
import logging
import urllib.parse
from typing import Optional, Tuple
import requests
from bs4 import BeautifulSoup
from engine.agents.base import BaseAgent
from engine.state import JobLead, ContactInfo
from engine.config import SERPER_API_KEY
from engine.tools.email_verifier import verify_and_clean_email, does_domain_exist, is_unhelpful_generic_email

logger = logging.getLogger("EnrichmentAgent")

class EnrichmentAgent(BaseAgent):
    """
    Enriches leads with decision-maker contact details (Name, Title, Email, LinkedIn).
    Uses Google Search (Serper API) + LLM entity extraction, website crawling,
    and enforces strict DNS deliverability checks so emails never bounce.
    """

    def __init__(self):
        super().__init__(name="EnrichmentAgent", role="Executive Contact Intelligence Specialist")

    def enrich(self, lead: JobLead) -> ContactInfo:
        """Discovers decision-maker contact details, with multi-role and social profile discovery."""
        effective_domain = lead.domain

        # 1. Multi-Persona & Social Discovery via Serper (Founders, Senior Engineers, Recruiters)
        personas = self._discover_socials_and_personas(lead.company)

        # Target primary persona (prefers Founder/CTO or Senior Engineer, then Recruiter)
        primary_persona = personas.get("founder") or personas.get("engineer") or personas.get("recruiter") or {}
        secondary_list = [p for k, p in personas.items() if p != primary_persona]

        # 2. Deterministic Source Hint (HN comment direct email or curated record)
        verified_email = ""
        enrichment_source = "Serper Social Profile Discovery (Direct ATS / Social Outreach)"

        if lead.direct_email_hint and "@" in lead.direct_email_hint:
            if not is_unhelpful_generic_email(lead.direct_email_hint):
                is_valid, clean_hint, reason = verify_and_clean_email(lead.direct_email_hint, allow_generic=False)
                if is_valid and clean_hint:
                    verified_email = clean_hint
                    enrichment_source = "Source Direct Mention (DNS Verified)"

        # 3. Google Search via Serper API + LLM Extraction (Finds true domain & contact email)
        if not verified_email:
            serper_email, serper_name, serper_title, real_dom = self._search_web_with_serper(lead.company, lead.domain)
            if real_dom:
                effective_domain = real_dom

            if serper_email and not is_unhelpful_generic_email(serper_email):
                is_valid, clean_serp, _ = verify_and_clean_email(serper_email, allow_generic=False)
                if is_valid and clean_serp:
                    verified_email = clean_serp
                    enrichment_source = "Google Search Verification (MX Verified)"
                    if not primary_persona:
                        primary_persona = {
                            "name": serper_name or "Hiring Lead",
                            "title": serper_title or "Talent Acquisition / Leadership",
                            "role_key": "recruiter"
                        }

        # 4. Deterministic Website Scraping (/about, /team, /company, /contact, /impressum)
        scraped_linkedin = None
        team_text = ""
        if not verified_email or not primary_persona:
            scraped_email, scraped_linkedin, team_text = self._crawl_company_website(effective_domain)
            if not verified_email and scraped_email and not is_unhelpful_generic_email(scraped_email):
                is_valid, clean_scraped, _ = verify_and_clean_email(scraped_email, allow_generic=False)
                if is_valid and clean_scraped:
                    verified_email = clean_scraped
                    enrichment_source = "Website Team Scraping (DNS Verified)"

        # 5. Targeted LLM Extraction (Only if scrape left ambiguous gaps)
        if not primary_persona:
            extracted_info = self._infer_leadership_contact(lead, team_text)
            founder_name = extracted_info.get("founder_name") or "Founder / CTO"
            founder_title = extracted_info.get("founder_title") or "Technical Decision Maker"
            primary_persona = {
                "name": founder_name,
                "title": founder_title,
                "role_key": "founder",
                "linkedin_url": scraped_linkedin or extracted_info.get("linkedin_url") or f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(founder_name + ' ' + lead.company)}",
                "twitter_url": ""
            }

        # Build ContactInfo with verified socials and multi-role profiles
        target_name = primary_persona.get("name") or "Founder / Hiring Lead"
        target_title = primary_persona.get("title") or "Engineering Decision Maker"
        target_li = primary_persona.get("linkedin_url") or f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(target_name + ' ' + lead.company)}"
        target_x = primary_persona.get("twitter_url") or ""
        role_cat = primary_persona.get("role_key") or "Leadership"

        socials_dict = {}
        if target_li:
            socials_dict["linkedin"] = target_li
        if target_x:
            socials_dict["twitter"] = target_x

        return ContactInfo(
            name=target_name,
            title=target_title,
            email=verified_email,
            linkedin_url=target_li,
            twitter_url=target_x,
            role_category=role_cat,
            socials=socials_dict,
            secondary_contacts=secondary_list,
            enrichment_source=enrichment_source
        )

    def _discover_socials_and_personas(self, company: str) -> dict:
        """
        Uses Serper to discover personal LinkedIn and X (Twitter) profiles for:
        1. Founders / Co-Founders / CTO / CEO
        2. Senior Software Engineers / Staff Engineers / Tech Leads / Engineering VPs
        3. Talent Acquisition / Technical Recruiters / HR
        """
        from engine.config import SERPER_API_KEY
        if not SERPER_API_KEY:
            return {}

        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
        url = "https://google.serper.dev/search"

        queries = [
            ("founder", f'site:linkedin.com/in/ OR site:x.com "{company}" ("Founder" OR "Co-Founder" OR "CTO" OR "CEO")'),
            ("engineer", f'site:linkedin.com/in/ OR site:x.com "{company}" ("Senior Software Engineer" OR "Staff Engineer" OR "Lead Engineer" OR "VP of Engineering")'),
            ("recruiter", f'site:linkedin.com/in/ OR site:x.com "{company}" ("Technical Recruiter" OR "Talent Acquisition" OR "Head of People" OR "HR")')
        ]

        personas = {}
        for role_key, q in queries:
            try:
                res = requests.post(url, headers=headers, json={"q": q, "num": 3}, timeout=6)
                if res.status_code != 200:
                    continue
                data = res.json()
                for item in data.get("organic", []):
                    title = item.get("title", "")
                    link = item.get("link", "")
                    snippet = item.get("snippet", "")

                    li_match = re.search(r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([a-zA-Z0-9_\-]+)', link)
                    x_match = re.search(r'https?://(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]{1,30})', link)
                    if not x_match:
                        x_in_snip = re.search(r'https?://(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]{1,30})', snippet)
                        if x_in_snip and x_in_snip.group(1).lower() not in ("search", "home", "explore", "intent", "hashtag"):
                            x_match = x_in_snip

                    clean_li = f"https://linkedin.com/in/{li_match.group(1)}" if li_match else ""
                    clean_x = f"https://x.com/{x_match.group(1)}" if x_match and x_match.group(1).lower() not in ("search", "home", "explore", "intent", "hashtag") else ""

                    clean_name = title.split("–")[0].split("-")[0].split("|")[0].strip()
                    clean_name = re.sub(r'\(.*?\)', '', clean_name).strip()

                    role_title = "Founder / CTO" if role_key == "founder" else ("Senior Engineer" if role_key == "engineer" else "Talent Acquisition")
                    if " - " in title:
                        parts = title.split(" - ")
                        if len(parts) > 1 and len(parts[1].strip()) < 60:
                            role_title = parts[1].strip()

                    if clean_name and (clean_li or clean_x) and role_key not in personas:
                        personas[role_key] = {
                            "name": clean_name,
                            "title": role_title,
                            "role_key": role_key,
                            "linkedin_url": clean_li,
                            "twitter_url": clean_x,
                            "snippet": snippet
                        }
                        break
            except Exception as e:
                logger.debug(f"Serper persona lookup failed for {role_key}: {e}")

        return personas

    def _extract_name_from_linkedin(self, url: str) -> Optional[str]:
        match = re.search(r'linkedin\.com/in/([a-zA-Z0-9_-]+)', url)
        if match:
            slug = match.group(1).replace("-", " ").replace("_", " ")
            slug_words = [w.capitalize() for w in slug.split() if not w.isdigit()]
            if slug_words:
                return " ".join(slug_words[:3])
        return None

    def _crawl_company_website(self, domain: str) -> Tuple[Optional[str], Optional[str], str]:
        if not domain:
            return None, None, ""

        clean_domain = domain.replace("http://", "").replace("https://", "").strip("/").split("/")[0]
        if not does_domain_exist(clean_domain):
            return None, None, ""

        base_url = f"https://{clean_domain}"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        paths = ["/about", "/team", "/company", "/contact", "/impressum", ""]
        scraped_emails = set()
        scraped_linkedins = set()
        combined_text = ""

        for path in paths:
            url = base_url + path
            try:
                res = requests.get(url, headers=headers, timeout=4, allow_redirects=True)
                if res.status_code == 200:
                    text = res.text
                    soup = BeautifulSoup(text, "html.parser")
                    clean_text = soup.get_text()[:2500]
                    combined_text += " " + clean_text

                    emails = re.findall(r'[a-zA-Z0-9_.+-]+@' + re.escape(clean_domain), text)
                    for e in emails:
                        e_low = e.lower()
                        if not e_low.startswith(("privacy@", "terms@", "abuse@", "legal@")):
                            scraped_emails.add(e_low)

                    linkedins = re.findall(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+', text)
                    for li in linkedins:
                        scraped_linkedins.add(li)

                    if scraped_emails or scraped_linkedins:
                        break
            except Exception:
                continue

        best_email = None
        if scraped_emails:
            valid_hiring = [e for e in scraped_emails if not is_unhelpful_generic_email(e)]
            preferred = [e for e in valid_hiring if any(h in e for h in ["careers@", "jobs@", "talent@", "hiring@", "recruiting@", "hr@", "founders@", "engineering@", "team@"])]
            if preferred:
                best_email = preferred[0]
            elif valid_hiring:
                best_email = valid_hiring[0]

        best_linkedin = list(scraped_linkedins)[0] if scraped_linkedins else None
        return best_email, best_linkedin, combined_text

    def _infer_leadership_contact(self, lead: JobLead, scraped_text: str) -> dict:
        prompt = f"""Identify the most likely technical leader or founder for outreach at {lead.company}.

Company: {lead.company}
Domain: {lead.domain}
Job Role: {lead.role}
Context / Web Snippets:
{lead.description[:1000]}
{scraped_text[:1000]}

Instructions:
1. Identify the name of the Founder, Co-Founder, CTO, or VP of Engineering.
2. If the exact name is mentioned in the text, use it.
3. Suggest the most probable direct email address (e.g. firstname@domain or founders@domain).
4. Provide a LinkedIn search URL or profile if available.

Return ONLY a JSON object with keys:
- founder_name: string (e.g. "Jane Doe" or "Founder / CTO")
- founder_title: string (e.g. "Co-Founder & CEO" or "CTO")
- suggested_email: string (e.g. "jane@company.com" or "founders@company.com")
- linkedin_url: string
"""
        try:
            return self.generate_json(prompt, system_prompt="You are an expert executive talent researcher.", temperature=0.2)
        except Exception as e:
            logger.warning(f"Leadership inference failed: {e}")
            return {}

    def _search_web_with_serper(self, company: str, domain: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        if not SERPER_API_KEY:
            return None, None, None, None

        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "q": f'"{company}" ("careers@" OR "jobs@" OR "talent@" OR "recruiting@" OR "hr@" OR "hiring@" OR "founders@")',
            "num": 6
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=8)
            if res.status_code == 403:
                logger.warning(f"Serper API returned 403 for {company} (Key expired or invalid on serper.dev).")
                return None, None, None, None
            if res.status_code != 200:
                logger.warning(f"Serper API query failed: {res.status_code} - {res.text[:80]}")
                return None, None, None, None

            data = res.json()
            organic = data.get("organic", [])
            if not organic:
                return None, None, None, None

            snippets = []
            for item in organic:
                t = item.get("title", "")
                link = item.get("link", "")
                snip = item.get("snippet", "")
                snippets.append(f"Title: {t}\nURL: {link}\nSnippet: {snip}")

            corpus = "\n\n".join(snippets)

            candidate_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', corpus)
            for cand in candidate_emails:
                cand_clean = cand.rstrip(".")
                if not any(x in cand_clean.lower() for x in ["example", "sentry", "schema", "w3.org", "png", "jpg"]):
                    if not is_unhelpful_generic_email(cand_clean):
                        is_valid, verified, _ = verify_and_clean_email(cand_clean, allow_generic=False)
                        if is_valid:
                            return verified, "Hiring Team", "Talent Acquisition", None

            prompt = f"""Analyze the following Google Search results for the company "{company}".
Find:
1. Contact email address for hiring or technical leadership (DO NOT include customer support, billing, or general info emails).
2. The real website domain of the company (e.g. "sdu.nl", "f-e.de", "bjak.my", "careship.de").
3. The name and title of the Founder, CEO, CTO, or Talent Lead if mentioned.

Google Search Snippets:
{corpus[:2000]}

Return ONLY a JSON object with keys:
- email: string (exact email or empty string)
- real_domain: string (e.g. "sdu.nl" or empty string)
- contact_name: string (e.g. "Jane Doe" or "Founder / CTO")
- contact_title: string (e.g. "Engineering Lead" or "Founder")
"""
            llm_data = self.generate_json(prompt, system_prompt="You are an expert executive talent researcher.", temperature=0.1)
            raw_email = llm_data.get("email", "").strip()
            real_dom = llm_data.get("real_domain", "").strip()
            name = llm_data.get("contact_name") or "Founder / CTO"
            title = llm_data.get("contact_title") or "Technical Decision Maker"

            if raw_email and not is_unhelpful_generic_email(raw_email):
                is_valid, verified, _ = verify_and_clean_email(raw_email, allow_generic=False)
                if is_valid:
                    return verified, name, title, real_dom

            return None, name, title, real_dom

        except Exception as e:
            logger.warning(f"Serper search failed for {company}: {e}")
            return None, None, None, None
