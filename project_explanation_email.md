Subject: Project Overview: Automated LLM in Evidence Synthesis Newsletter

Hi [Recipient Name],

I wanted to share a quick overview of the **Evidence Synthesis LLM Newsletter** project I've been working on.

**The Problem**
The intersection of Large Language Models (LLMs) and Evidence Synthesis (systematic reviews, meta-analyses) is moving incredibly fast. Keeping up with new papers, tools, and discussions across fragmented sources (journals, preprints, blogs, GitHub) is becoming impossible to do manually.

**The Solution**
I built an automated Python pipeline that acts as a comprehensive research assistant. It scans the web weekly for everything related to "LLMs in Evidence Synthesis" and compiles it into a curated newsletter.

**How It Works**
1.  **Broad Surveillance:** The system queries multiple sources to ensure high recall:
    *   **Academic Databases:** PubMed, OpenAlex, Crossref, arXiv.
    *   **Grey Literature:** Google Search (for blogs/news), Twitter/X discussions, and RSS feeds.
    *   **Code:** GitHub repositories for new tools.
2.  **AI Analysis:** It uses an LLM (GPT-4o) to read the abstracts, categorize them (e.g., *New Tools*, *Methodology*, *Benchmarks*), and write concise, informative summaries.
3.  **Human-in-the-Loop:** Before publishing, the system pauses and generates a draft file. I review this to filter out noise and tweak summaries, ensuring high quality.
4.  **Output:** It automatically generates a formatted HTML and Markdown newsletter ready for distribution.

**Key Features**
*   **"Grey Literature" Focus:** Unlike standard alerts, this catches blog posts and software releases that often precede formal publication.
*   **Smart Deduplication:** Merges duplicate records from different sources.
*   **Open Access Checking:** Automatically finds free PDF links for papers.

It’s currently running locally and helping me stay on top of the field with minimal manual effort.

Best,

[Your Name]