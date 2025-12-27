from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import List, Dict, Any
import json

class Extractor:
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

    def extract_pico(self, text: str) -> Dict[str, str]:
        if not self.llm:
            return {"P": "Population", "I": "Intervention", "C": "Comparator", "O": "Outcome"}

        prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract the PICO (Population, Intervention, Comparator, Outcome) elements from the following text. Return ONLY a JSON object, with no additional text or markdown formatting."),
            ("user", "{text}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            result = chain.invoke({"text": text})
            # Clean result if it has markdown code blocks
            cleaned_result = result.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_result)
        except Exception as e:
            print(f"Extraction error: {e}")
            print(f"Raw result: {result}")
            return {}

def extract_data(records: List[Dict[str, Any]], extractor: Extractor) -> List[Dict[str, Any]]:
    for record in records:
        # In a real scenario, we'd use the full text here. Using abstract for now.
        text = record.get('abstract') or record.get('title')
        pico = extractor.extract_pico(text)
        record['extraction'] = pico
    return records
