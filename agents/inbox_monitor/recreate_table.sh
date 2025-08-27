#!/bin/bash
# Simple wrapper script to recreate table from model
# This ensures the script runs from the correct directory with proper environment

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔧 Running Table Recreation Script from: $(pwd)"
echo "📋 Environment check:"

# Check if key environment variables are set
if [[ -z "$DATABRICKS_SERVER_HOSTNAME" ]]; then
    echo "❌ DATABRICKS_SERVER_HOSTNAME not set"
    echo "💡 Make sure you're running this from a properly configured shell session"
    exit 1
else
    echo "✅ DATABRICKS_SERVER_HOSTNAME: $DATABRICKS_SERVER_HOSTNAME"
fi

if [[ -z "$DATABRICKS_CATALOG" ]]; then
    echo "❌ DATABRICKS_CATALOG not set"
    exit 1
else
    echo "✅ DATABRICKS_CATALOG: $DATABRICKS_CATALOG"
fi

if [[ -z "$AZURE_KEY_VAULT_URL" ]]; then
    echo "❌ AZURE_KEY_VAULT_URL not set"
    exit 1
else
    echo "✅ AZURE_KEY_VAULT_URL: $AZURE_KEY_VAULT_URL"
fi

echo ""
echo "🚀 Starting table recreation..."

# Run the Python script with auto-confirmation
AUTO_CONFIRM_DROP_TABLE=true python utils/recreate_table_from_model.py

exit_code=$?

if [[ $exit_code -eq 0 ]]; then
    echo ""
    echo "🎉 Table recreation completed successfully!"
    echo "   Your table now matches your ScenarioProcessingRecord model exactly."
else
    echo ""
    echo "❌ Table recreation failed with exit code: $exit_code"
    echo "   Check the error messages above for details."
fi

exit $exit_code