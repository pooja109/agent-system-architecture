#!/usr/bin/env python3
"""
Delete existing Azure AI Foundry Agent
======================================

Script to delete the existing agent so we can recreate it with correct model.
"""

import asyncio
import os

from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import AzureAIAgent


async def delete_existing_agent():
    """Delete the existing email-intent-classifier agent."""

    # Set environment variables
    os.environ[
        "AZURE_AI_AGENT_ENDPOINT"
    ] = "https://ai-lowtouch-foundry.services.ai.azure.com/api/projects/LowTouch"
    os.environ["AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"] = "gpt-4o"

    async with DefaultAzureCredential() as creds:
        async with AzureAIAgent.create_client(credential=creds) as client:
            # Find the existing agent
            agents_pager = client.agents.list_agents()
            agent_to_delete = None

            async for agent_def in agents_pager:
                if agent_def.name == "email-intent-classifier":
                    agent_to_delete = agent_def
                    print(f"Found existing agent: {agent_def.id}")
                    break

            if agent_to_delete:
                try:
                    await client.agents.delete_agent(agent_to_delete.id)
                    print(f"Successfully deleted agent: {agent_to_delete.id}")
                except Exception as e:
                    print(f"Error deleting agent: {e}")
            else:
                print("No existing agent found")


if __name__ == "__main__":
    asyncio.run(delete_existing_agent())
