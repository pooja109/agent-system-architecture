import os, sys

from utils import azureblobhelper, azurequeuehelper



# Add utilities to path
'''
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))
print("Utils Path: ",os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))

try:
    from azureblobhelper import AzureBlobHelper
    from azurequeuehelper import AzureQueueHelper

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure to install required packages: pip install -r utils/requirements.txt")
    sys.exit(1)
'''