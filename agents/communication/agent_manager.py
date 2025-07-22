"""
Agent manager for creating and managing AI agents.
"""
import asyncio
import time
import logging
import sys
import os
from colorama import Fore, Style


from agents.communication.agents import sk_email_gen_agent
from agents.communication.agents import sk_email_review_agent
from agents.communication.agents import sk_data_extractor_agent
from agents.communication.agents import sk_emailpercontact_gen_agent

logger = logging.getLogger(__name__)

class AgentManager:
    """Manages the creation and lifecycle of AI agents."""
    
    def __init__(self):
        self.data_extractor_agent = None
        self.email_generator_agent = None
        self.email_review_agent = None
        self.per_contact_email_agent = None
    
    async def create_agents(self):
        """Create all required agents in parallel."""
        agent_creation_start_time = time.time()
        logger.info("%s🔄 Creating agents in parallel...%s", Fore.YELLOW, Style.RESET_ALL)
        
        # Create agents using the provided functions
        (self.data_extractor_agent, 
         self.email_generator_agent, 
         self.email_review_agent, 
         self.per_contact_email_agent) = await asyncio.gather(
            sk_data_extractor_agent.get_data_agent(),
            sk_email_gen_agent.get_email_agent(),
            sk_email_review_agent.get_email_review_agent(),
            sk_emailpercontact_gen_agent.get_email_agent(),
        )
        
        agent_creation_duration = time.time() - agent_creation_start_time
        logger.info("%s[SUCCESS] All agents created successfully!%s", Fore.GREEN, Style.RESET_ALL)
        logger.info("%s[TIMING] Agent creation time: %.3f seconds%s", Fore.CYAN, agent_creation_duration, Style.RESET_ALL)
        
        return (self.data_extractor_agent, 
                self.email_generator_agent, 
                self.email_review_agent, 
                self.per_contact_email_agent)
    
    def get_agents(self):
        """Get all created agents as a tuple."""
        return (self.data_extractor_agent, 
                self.email_generator_agent, 
                self.email_review_agent, 
                self.per_contact_email_agent)
