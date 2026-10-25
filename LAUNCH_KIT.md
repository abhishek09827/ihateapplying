# 🚀 AI Outreach Engine — Viral Launch & Marketing Kit

This launch kit contains ready-to-publish social copy, launch posts, and marketing materials designed to drive GitHub stars, community contributions, and viral adoption across developer and tech communities.

---

## 🐦 1. Twitter / X Launch Thread (High-Converting 5-Tweet Thread)

### Tweet 1 (The Hook):
> I got tired of sending 200+ applications into ATS black holes and hearing nothing back.
>
> So I built an open-source, multi-agent AI system that:
> 🔍 Scouts hidden openings & funded startups
> 🎯 Screens for 1-3 yr seniority fit
> ✉️ Finds founder emails & compiles custom PDF resumes
> 🚀 Sends emails directly on autopilot OR creates reviewable drafts in Gmail
>
> It runs 100% on free-tier APIs ($0/mo).
>
> 🧵 Here's how it works + GitHub link: 👇

### Tweet 2 (The Multi-Agent Architecture):
> Most "AI job tools" blast generic spam with ChatGPT. That gets you blocked.
>
> This engine runs 5 specialized agents:
> 1. Job Scout: Scrapes RemoteOK, Remotive, Jobicy & HN "Who is Hiring"
> 2. Screener: Sub-millisecond regex + Groq LLM filter
> 3. Enricher: Google Serper + DNS MX deliverability verifier
> 4. Crafter: Compiles tailored Typst PDF resumes in 300ms
> 5. Dispatcher: Sends emails directly via Gmail SMTP (with anti-spam throttling) OR stages drafts for 1-click review

### Tweet 3 (The 100% Free Stack):
> You can run this indefinitely for $0.00/month:
>
> ⚡ Groq: 14,400 free daily LLM requests (`openai/gpt-oss-120b`)
> 🔍 Serper: 2,500 free Google searches for email finding
> 📄 Typst: Sub-second native PDF compilation (no LaTeX bloat)
> 📊 Notion: Real-time application tracking CRM
> ☁️ GitHub Actions: 2,000 free runner minutes/month

### Tweet 4 (Fork & Run in 3 Minutes):
> You don't even need to clone it locally:
>
> 1. Fork the repo on GitHub
> 2. Edit `config/profile.json` with your target roles & links
> 3. Add your free Groq API key in Repo Settings > Secrets
> 4. Click "Actions" > "Run workflow"
>
> Choose your autonomy: Let it send emails directly on autopilot, or create drafts in your Gmail for 1-click review!

### Tweet 5 (Call to Action):
> It's 100% open-source under MIT License.
>
> ⭐ Star the repo, fork it, and land more interviews this week:
>
> 🔗 https://github.com/your-username/ai-outreach-engine
>
> What features should we add next? Auto-followups? Let me know below! 👇

---

## 💼 2. LinkedIn Post (Story-Driven & High Engagement)

**Copy:**
```text
The tech job market in 2026 is broken. 

Submitting generic resumes to 300+ LinkedIn job postings rarely works. By the time a role is 2 hours old, it already has 800+ applicants. The resume scanner rejects 95% of them before a human ever sees them.

The candidates actually getting interviews are doing something different:
Direct, thoughtful outreach to founders, VP of Engineering, and hiring leads with tailored resumes and concrete proof of work.

The catch? Doing that manually takes 25 minutes per company.

Over the past few weeks, I built an open-source Autonomous AI Outreach Engine that handles the entire pipeline autonomously:

🤖 1. Multi-Channel Discovery: Scouts live postings across RemoteOK, Remotive, Hacker News "Who is Hiring", and newly funded venture feeds.
🎯 2. Seniority & Role Guard: Rejects unrealistic 7+ year senior roles in <0.001s, focusing strictly on roles matching your level.
🔍 3. Executive Lead Enrichment: Uses Google search intelligence and DNS MX checks to verify real founder/lead engineer emails.
📄 4. Native Typst Resume Compiler: Compiles a unique, ATS-compliant 1-page PDF resume tailored to each company's tech stack in sub-second time.
✉️ 5. Dual Dispatch Modes (Full Autopilot or Draft Review):
   • 🔥 Direct Send Autopilot: Sends emails directly via Gmail SMTP with tailored PDF resumes attached and anti-spam pacing (15s safe throttle).
   • 🛡 Draft-First Safety: Stages polished drafts in your Gmail for 1-click human verification before sending.

Best part? It runs 100% on free-tier APIs ($0/month):
• Groq (14,400 free requests/day)
• Typst (sub-second PDF rendering)
• Notion API (bidirectional CRM)
• GitHub Actions (runs twice daily without hosting a server)

You can literally fork the repo, update `config/profile.json`, and click "Run Workflow" in GitHub Actions.

The code is 100% open-source under MIT:
👉 https://github.com/your-username/ai-outreach-engine

If you're currently job hunting or know someone who is, check it out and feel free to star the repo!

#OpenSource #ArtificialIntelligence #SoftwareEngineering #CareerGrowth #Python #JobSearch #TechHiring
```

---

## 👾 3. Reddit Post (for r/Python, r/SideProject, r/webdev, r/cscareerquestions)

**Title:**
> I got tired of applying to 100s of ATS black holes, so I built an open-source multi-agent engine that compiles custom resumes and sends direct emails or stages Gmail drafts ($0/mo free stack)

**Post Body:**
```markdown
Hey everyone!

Like many engineers here, I experienced the frustration of submitting applications into automated ATS systems that feel like black holes. Cold outreach directly to founders and engineering managers had a 10x higher response rate for me, but writing personalized emails and tailoring resumes took hours every day.

So I built **AI Outreach Engine**, an open-source multi-agent system written in Python that automates the entire process:

### How it works:
1. **Multi-Platform Scout**: Pulls fresh jobs and funding announcements from RemoteOK, Remotive, Jobicy, and Hacker News *Who is Hiring*.
2. **Deterministic & LLM Screening**: First runs a regex filter to reject Senior/Staff/Director roles and seniority mismatches, then scores the remaining jobs against your profile.
3. **Contact Enrichment & DNS MX Verification**: Uses Google Serper API + direct web crawling to find hiring manager names and emails, and validates them against public DNS MX records to prevent bounces.
4. **Dynamic Typst PDF Resume Compilation**: Instead of slow LaTeX, it uses [Typst](https://typst.app) (compiled via Python bindings) to generate a customized 1-page PDF resume in <0.5 seconds for each company.
5. **Dual Dispatch Modes**:
   - **Direct Send Autopilot**: Sends emails directly via Gmail SMTP with tailored PDF resumes attached and built-in anti-spam pacing (15s safe delay).
   - **Draft Review Mode**: Stages drafts in your Gmail Drafts folder so you can inspect and 1-click send them yourself.
6. **Notion CRM Sync**: Records every company, contact, match score, and status in Notion.

### The 100% Free Stack:
- **Groq** (`openai/gpt-oss-120b`): 14,400 free requests/day.
- **Serper.dev**: 2,500 free Google searches.
- **Typst**: Native open-source typesetter.
- **GitHub Actions**: 2,000 free minutes/month to run on a twice-daily schedule without a VPS.

### Fork & Run (No local setup required):
You can fork the repository, edit `config/profile.json` in the browser, add your free Groq key in repo secrets, and trigger the workflow directly from the Actions tab.

GitHub: https://github.com/your-username/ai-outreach-engine

I’d love to hear your feedback on the architecture, prompt design, and any features you'd like to see added!
```

---

## 🟠 4. Hacker News (Show HN)

**Title:**
> Show HN: AI Outreach Engine – Autonomous multi-agent job application engine using Groq and Typst

**Body:**
```text
Hi HN,

I built an open-source multi-agent tool in Python that scouts tech jobs, enriches hiring manager emails, compiles tailored 1-page PDF resumes using Typst, and either sends emails directly or stages Gmail drafts:

https://github.com/your-username/ai-outreach-engine

Why I built this:
Submitting through ATS forms is notoriously low-signal. High-converting outreach requires personalized emails citing specific engineering achievements and tailored resumes matching the exact tech stack. But doing this manually doesn't scale.

Architectural highlights:
- Multi-Agent Pipeline: Discovery -> Screening -> Enrichment -> Resume Compilation -> Dispatch.
- Typst over LaTeX: Uses Typst Python bindings to compile clean, ATS-compliant PDFs in ~300ms without needing a 2GB TeX Live distribution.
- DNS MX Deliverability: Validates discovered emails against DNS MX and disposable domain blocklists to minimize bounce rates.
- Dual Dispatch: Full hands-off direct outreach via Gmail SMTP (with anti-spam rate limiting) OR human-in-the-loop draft staging via IMAP.
- 100% Free Tier: Powered by Groq's free tier (14.4k req/day), Serper (2.5k free searches), and GitHub Actions scheduled cron.

Code and setup instructions: https://github.com/your-username/ai-outreach-engine

Would love any thoughts on the agent orchestration and email deliverability checks!
```

---

## 🐱 5. Product Hunt Launch Copy

- **Product Name**: AI Outreach Engine
- **Tagline**: Autonomous multi-agent job outreach engine (100% free tier)
- **Pricing**: Free / Open Source (MIT)
- **Short Description**: Discovers hidden openings, enriches founder emails, compiles tailored Typst PDF resumes, and either sends emails directly via Gmail SMTP or stages reviewable drafts—all powered by free-tier AI APIs.

### First Comment from Maker:
> Hey Product Hunt community! 👋
> 
> As software engineers, we spend years honing our technical skills, only to spend weeks submitting resumes into ATS black holes that filter by arbitrary keywords.
> 
> I built **AI Outreach Engine** to flip the script. It's a 100% open-source multi-agent system that helps engineers reach founders and hiring managers directly with hyper-tailored resumes and personalized pitches.
> 
> Key features:
> • 100% Free Stack: Powered by Groq, Typst, and GitHub Actions ($0/month).
> • Dual Dispatch Modes: Autopilot direct send via Gmail SMTP OR reviewable drafts.
> • Fork & Run: Fork the repo, edit `config/profile.json`, and run in GitHub Actions in under 3 minutes.
> 
> Try it out and let us know what you think! 🚀
