from __future__ import annotations

import asyncio
import json
import os
import logging
from dotenv import load_dotenv
from openai import OpenAI, AsyncAzureOpenAI, AsyncOpenAI, AzureOpenAI
# Load environment variables from .env file before they are accessed
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file before they are accessed
load_dotenv()
from pydantic import BaseModel, Field
from typing import Dict, List, Literal, Optional

class WebSearchResultsExtraction(BaseModel):
    is_relevant: bool
    matched_fields: list[str]
    why: str
    search_results: str

# New Pydantic models for parsing the full response structure
class UrlCitation(BaseModel):
    url: str
    title: str

class Annotation(BaseModel):
    type: str
    text: str
    start_index: int
    end_index: int
    url_citation: UrlCitation

class TextContent(BaseModel):
    value: str
    annotations: List[Annotation]

class ContentItem(BaseModel):
    type: str
    text: TextContent

class MessageResponse(BaseModel):
    id: str
    object: str
    created_at: int
    assistant_id: str
    thread_id: str
    run_id: str
    role: str
    content: List[ContentItem]
    attachments: List[Dict]
    metadata: Dict

async def filter_results_with_llm(
        results: List[Dict], profile: Dict
    ) -> List[WebSearchResultsExtraction]:
        filtered = []
        system_prompt = """
                You are a filter whose only job is:
                "Given a customer profile and one search result, say whether this result is about that customer—or a namesake in another industry."
                Respond *only* in JSON with fields:
                - is_relevant: true|false
                - matched_fields: list of profile keys you detected (e.g. ["industry","domain_hint"])
                - why: one-sentence justification
                - search_results: the full search result snippet as-is.
                """
        review_results:List[WebSearchResultsExtraction] = []
        for result in results:
            user_prompt = f"""
                    Customer Profile:
                    {json.dumps(profile, indent=2)}
                    Search Result:
                    Title: {result['title']}
                    URL: {result['url']}
                    Snippet: {result['snippet']}
                    Respond in JSON:
                    """
            client = OpenAI(
            api_key=os.getenv("ST_AZURE_OPENAI_API_KEY"),
            default_query={"api-version": "preview"},
            base_url=os.getenv("ST_AZURE_OPENAI_ENDPOINT"),
            )


            client = AzureOpenAI(api_version=os.getenv("ST_API_VERSION"),    
                     azure_endpoint=os.getenv("ST_AZURE_OPENAI_ENDPOINT"),    
                     api_key=os.getenv("ST_AZURE_OPENAI_API_KEY"))

            response = client.responses.parse(
                model=  "gpt-4o",                                    #"gpt-4.1",
                input=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": user_prompt},
                ],
                text_format=WebSearchResultsExtraction,
            )
            # response = client.responses.create(
            #     model="gpt-4.1",
            #     input=[
            #         {
            #             "role": "system",
            #             "content": system_prompt,
            #         },
            #         {"role": "user", "content": user_prompt},
            #     ]
            # )
            #print(response.model_dump_json(indent=2)) 
            logger.info(response.output_parsed)
            review_results.append(response.output_parsed)
        return review_results

def extract_search_results_from_message(message_data: Dict) -> List[Dict[str, str]]:
    """
    Extract URL, title, and text value from the message response structure.
    Returns a list of dictionaries with 'url', 'title', and 'snippet' keys.
    """
    extracted_results = []

    # Parse the message using Pydantic
    try:
        message = MessageResponse(**message_data)
        for content_item in message.content:
            if content_item.type == 'text':
                text_value = content_item.text.value
                # Extract each annotation's URL and title, along with the text value
                for annotation in content_item.text.annotations:
                    if annotation.type == 'url_citation':
                        extracted_results.append({
                            'url': annotation.url_citation.url,
                            'title': annotation.url_citation.title,
                            'snippet': text_value  # Using the full text value as snippet
                        })
    except Exception as e:
        logger.error(f"Error parsing message: {e}")
        # Fallback: standard Python parsing
        try:
            for content_item in message_data.get('content', []):
                if content_item.get('type') == 'text':
                    text_value = content_item['text']['value']
                    for annotation in content_item['text'].get('annotations', []):
                        if annotation.get('type') == 'url_citation':
                            url_citation = annotation.get('url_citation', {})
                            extracted_results.append({
                                'url': url_citation.get('url', ''),
                                'title': url_citation.get('title', ''),
                                'snippet': text_value
                            })
        except Exception as fallback_error:
            logger.error(f"Fallback parsing also failed: {fallback_error}")

    return extracted_results

async def review_research(CUSTOMER_PROFILE: dict, sample_message: dict) -> List[WebSearchResultsExtraction]:
    """
    Review research results for a given customer profile and message data.
    Args:
        CUSTOMER_PROFILE: dict containing customer profile information
        sample_message: dict containing the message data with search results
    Returns:
        List[WebSearchResultsExtraction]: filtered and parsed results
    """
    # Extract search results from the message
    results = extract_search_results_from_message(sample_message)

    logger.info("Extracted results:")
    for i, result in enumerate(results):
        logger.info(f"Result {i+1}:")
        logger.info(f"  URL: {result['url']}")
        logger.info(f"  Title: {result['title']}")
        logger.info(f"  Snippet: {result['snippet'][:100]}...")  # Show first 100 chars
        logger.info("")

    # Now filter the results with LLM
    filtered_results = await filter_results_with_llm(results, CUSTOMER_PROFILE)
    return filtered_results