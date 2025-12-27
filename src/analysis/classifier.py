from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import List, Dict, Any
import json

class Classifier:
    def __init__(self, api_key: str, model_name: str = "gpt-4o", base_url: str = None):
        print(f"DEBUG: Classifier init with key length: {len(api_key) if api_key else 0}")
        if api_key == "YOUR_OPENROUTER_API_KEY" or api_key == "YOUR_OPENAI_API_KEY":
             print("DEBUG: Using placeholder key, LLM disabled.")
             self.llm = None
        else:
            print(f"DEBUG: Initializing ChatOpenAI with model {model_name} and base_url {base_url}")
            try:
                self.llm = ChatOpenAI(
                    api_key=api_key, 
                    model=model_name, 
                    temperature=0,
                    base_url=base_url
                )
            except Exception as e:
                print(f"DEBUG: Error initializing ChatOpenAI: {e}")
                self.llm = None
        
        self.taxonomy = [
            "screening/triage",
            "PICO extraction",
            "risk of bias",
            "data extraction",
            "evidence-to-decision (GRADE)",
            "reporting/PRISMA"
        ]

    def classify(self, title: str, abstract: str) -> List[str]:
        if not self.llm:
            return ["screening/triage"] # Default for testing

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert in evidence synthesis. Classify the following paper into one or more of these categories: {taxonomy}. Return ONLY a JSON list of strings, with no additional text or markdown formatting."),
            ("user", "Title: {title}\nAbstract: {abstract}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            result = chain.invoke({
                "taxonomy": ", ".join(self.taxonomy),
                "title": title,
                "abstract": abstract or "No abstract available"
            })
            # Clean result if it has markdown code blocks
            cleaned_result = result.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_result)
        except Exception as e:
            print(f"Classification error: {e}")
            print(f"Raw result: {result}")
            return []

def classify_records(records: List[Dict[str, Any]], classifier: Classifier) -> List[Dict[str, Any]]:
    for record in records:
        tags = classifier.classify(record.get('title'), record.get('abstract'))
        record['classification'] = tags
    return records
