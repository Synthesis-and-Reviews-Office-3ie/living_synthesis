# LLM Evidence Synthesis Newsletter Generator

This tool automates the creation of a weekly newsletter tracking the intersection of **Large Language Models (LLMs)** and **Evidence Synthesis**. It scans scholarly databases, filters for relevance, and uses an LLM Agent to write summaries, extract key models, and categorize papers for a Substack-style digest.

## Features

- **Multi-Source Ingestion**: Fetches the latest research from **OpenAlex**, **PubMed**, **Crossref**, **arXiv**, **GitHub**, and **Google Search**.
- **Smart Deduplication**: Merges records by DOI to avoid duplicates.
- **Open Access Discovery**: Automatically finds PDF links using the **Unpaywall API**.
- **AI Editor**: An LLM Agent (via OpenRouter/OpenAI) that:
    - Writes catchy, practitioner-focused headlines.
    - Summarizes the "so what?" for evidence synthesis.
    - Categorizes items (e.g., "New Tool", "Methodology", "Benchmark").
    - Extracts mentioned models (e.g., GPT-4, Llama 3).
    - Scores relevance to filter out noise.
- **Markdown Output**: Generates a ready-to-publish `newsletter_draft.md` file.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    - Edit `config/settings.yaml`:
        - Add your **OpenRouter API Key** (or OpenAI Key).
        - Add your email for Unpaywall (required).
        - (Optional) Add OpenAlex/PubMed keys for higher rate limits.
        - (Optional) Add **Google Custom Search API Key** and **CX** (Search Engine ID) to enable web/blog search.
        - (Optional) Add **GitHub Token** for higher rate limits on repo search.

    > **Note:** Google Scholar is not directly supported due to lack of an official API. Twitter/X integration requires a paid Enterprise API key.

3.  **Database (Optional)**:
    - The script defaults to in-memory storage if no Postgres database is found, so you can run it immediately.
    - To use Postgres, update the `connection_string` in `config/settings.yaml`.

4.  **Run the Pipeline**:
    ```bash
    python main.py
    ```

## Output

The script generates a file named `newsletter_draft.md` in the root directory. 

**Example Output:**

> ## New Tool/App
>
> ### MetaBeeAI: An AI pipeline for full-text systematic reviews
> **Relevance:** 9/10 | **Models:** GPT-4, BioBERT
>
> This paper introduces a new open-source pipeline that automates data extraction from full-text PDFs, achieving 85% accuracy compared to human reviewers. It's a significant step for living systematic reviews.
>
> 🔗 [DOI](https://doi.org/...) | [PDF](https://...)

## Project Structure

- `src/ingestion`: Fetchers for OpenAlex, PubMed, Crossref.
- `src/processing`: Deduplication and Unpaywall enrichment.
- `src/analysis`: `newsletter_analyzer.py` containing the LLM prompting logic.
- `config`: Configuration settings.
- `main.py`: The main orchestration script.

## License

MIT
