"""
Refactored Communication Agent using modular design.
"""
import asyncio
import sys
import os
from colorama import init

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Add the parent directory to the Python path to find the agents module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Initialize colorama for cross-platform colored terminal output
init(autoreset=True)

# Import local modules
from config import LoggingConfig
from communication_manager import CommunicationManager


async def main():
    """Main function to run the communication agent."""
    manager = CommunicationManager()
    await manager.run()

if __name__ == "__main__":
    # Configure logging
    LoggingConfig.configure_logging()
    
    # Run the main function
    asyncio.run(main())