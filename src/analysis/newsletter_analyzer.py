from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import List, Dict, Any
import json
from tqdm import tqdm

class NewsletterAnalyzer:
    def __init__(self, api_key: str, model_name: str = "gpt-4o", base_url: str = None):
        if api_key == "YOUR_OPENROUTER_API_KEY" or api_key == "YOUR_OPENAI_API_KEY":
             self.llm = None
        else:
            self.llm = ChatOpenAI(
                api_key=api_key, 
                model=model_name, 
                temperature=0,
                base_url=base_url
            )

    def analyze(self, title: str, abstract: str) -> Dict[str, Any]:
        if not self.llm:
            return {
                "headline": title,
                "summary": "Summary placeholder.",
                "category": "Research Paper",
                "models": [],
                "relevance_score": 5
            }

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the editor of a newsletter called 'LLMs in Evidence Synthesis'. 
            Your goal is to identify **only** papers that present a **methodological innovation** or a **new tool** for using Large Language Models (LLMs) in the process of evidence synthesis (systematic reviews, meta-analyses, etc.).

            **Strict Inclusion Criteria:**
            - The paper must DEVELOP or EVALUATE a method/tool using LLMs for tasks like: screening, data extraction, risk of bias assessment, search strategy generation, or synthesis.
            - The paper must be about the *methodology* of evidence synthesis, not just a review on a medical topic.
            - **NEW:** Include general AI tools (like "DeepScholar", "Research Assistants", "PDF Analyzers") **IF AND ONLY IF** they have clear potential to automate parts of the systematic review process (e.g., reading 100s of papers, extracting data tables), even if they don't explicitly say "systematic review".

            **Strict Exclusion Criteria:**
            - Exclude standard systematic reviews on clinical/social topics (even if they mention "synthesis").
            - Exclude general "AI in healthcare" papers unless they specifically address evidence synthesis methods.
            - Exclude papers that just *use* an LLM to write a paper without discussing the method.

            Analyze the following text and extract:
            1. "headline": A professional, descriptive headline (max 10 words). DO NOT use hype words like 'Revolutionizing', 'Game-changer', 'Unleashing', 'Transforming'.
            2. "summary": A concise but informative paragraph (3-4 sentences). Explicitly state the specific problem addressed, the method/tool proposed, and the key results or capabilities. Avoid promotional language but be specific about what the tool does.
            3. "category": Choose one of ['New Tool/App', 'Methodology', 'Review/Benchmark', 'Opinion/Discussion'].
            4. "models": A list of specific LLMs mentioned (e.g., 'GPT-4', 'Llama 2', 'Claude').
            5. "relevance_score": An integer 1-10. 
               - **8-10**: A new tool or method specifically for evidence synthesis (e.g., "Automating screening with GPT-4") OR a powerful general research tool (e.g., "DeepScholar").
               - **5-7**: A benchmark or review of LLMs in this field.
               - **1-4**: Irrelevant (e.g., a medical review, general AI paper).
            
            Return ONLY a JSON object, with no additional text or markdown formatting."""),
            ("user", "Title: {title}\nAbstract: {abstract}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            result = chain.invoke({"title": title, "abstract": abstract or "No abstract provided."})
            # Clean result if it has markdown code blocks
            cleaned_result = result.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_result)
        except Exception as e:
            print(f"Analysis error: {e}")
            return {}

def analyze_records(records: List[Dict[str, Any]], analyzer: NewsletterAnalyzer) -> List[Dict[str, Any]]:
    print(f"Analyzing {len(records)} records for newsletter content...")
    analyzed = []
    for record in tqdm(records):
        # Skip records with no title
        if not record.get('title'):
            continue
            
        analysis = analyzer.analyze(record.get('title'), record.get('abstract'))
        
        # Filter out low relevance items immediately
        # Threshold raised to 7 to ensure only methodological innovations are included
        if analysis.get('relevance_score', 0) >= 7:
            record['newsletter_content'] = analysis
            analyzed.append(record)
            
    return analyzed
