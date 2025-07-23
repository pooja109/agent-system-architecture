#!/usr/bin/env python3
"""
Debug Azure AI Foundry Response Structure
=========================================

Script to examine the actual structure of response objects from Azure AI Foundry
to understand how to properly extract the content.
"""

import asyncio
import os

from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import AzureAIAgent


async def debug_response_structure():
    """Debug the structure of Azure AI Foundry agent responses."""

    # Set environment variables
    os.environ[
        "AZURE_AI_AGENT_ENDPOINT"
    ] = "https://ai-lowtouch-foundry.services.ai.azure.com/api/projects/LowTouch"
    os.environ["AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"] = "gpt-4o"

    async with DefaultAzureCredential() as creds:
        async with AzureAIAgent.create_client(credential=creds) as client:
            # Find the existing agent
            agents_pager = client.agents.list_agents()
            agent_def = None

            async for agent in agents_pager:
                if agent.name == "email-intent-classifier":
                    agent_def = agent
                    print(f"Found agent: {agent.id}")
                    break

            if not agent_def:
                print("No agent found")
                return

            # Create agent instance
            ai_agent = AzureAIAgent(client=client, definition=agent_def)

            # Test with a simple message
            test_prompt = """
Please analyze this email response and classify the sender's intent:

EMAIL DETAILS:
From: test@example.com
Subject: Test Classification
Body: This is a test message to understand response structure.

Analyze the overall context, tone, and meaning to determine the sender's true intent. Provide your classification in the JSON format specified in your instructions.
""".strip()

            print("Sending test message to agent...")
            response = await ai_agent.get_response(messages=[test_prompt])

            print("\n=== RESPONSE ANALYSIS ===")
            print(f"Response type: {type(response)}")
            print(f"Response dir(): {dir(response)}")

            # Try different attribute access patterns
            attributes_to_check = [
                "content",
                "value",
                "text",
                "message",
                "data",
                "result",
                "choices",
                "output",
                "completion",
                "answer",
                "response",
            ]

            for attr in attributes_to_check:
                if hasattr(response, attr):
                    attr_value = getattr(response, attr)
                    print(f"\nFound attribute '{attr}': {type(attr_value)}")
                    if hasattr(attr_value, "__dict__"):
                        print(f"  {attr} attributes: {dir(attr_value)}")

                    # If it's a list, examine first item
                    if isinstance(attr_value, list) and len(attr_value) > 0:
                        first_item = attr_value[0]
                        print(f"  First item type: {type(first_item)}")
                        print(f"  First item dir: {dir(first_item)}")
                        if hasattr(first_item, "content"):
                            print(f"  First item content: {first_item.content}")

                    # Try to convert to string and check if it contains JSON
                    try:
                        str_value = str(attr_value)
                        if "{" in str_value and "}" in str_value:
                            print(f"  {attr} as string (first 200 chars): {str_value[:200]}")
                    except:
                        pass

            # Try to access response.messages if it exists
            if hasattr(response, "messages"):
                messages = response.messages
                print(f"\nMessages type: {type(messages)}")
                if isinstance(messages, list) and len(messages) > 0:
                    last_message = messages[-1]
                    print(f"Last message type: {type(last_message)}")
                    print(f"Last message dir: {dir(last_message)}")

                    # Check for content in message
                    if hasattr(last_message, "content"):
                        content = last_message.content
                        print(f"Message content type: {type(content)}")
                        print(f"Message content: {content}")


if __name__ == "__main__":
    asyncio.run(debug_response_structure())
