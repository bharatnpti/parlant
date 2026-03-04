#!/usr/bin/env python3
"""
Test script to verify Azure OpenAI request/response logging functionality.
This script demonstrates how to use the updated azure_service.py with detailed logging.
"""

import parlant.sdk as p
import asyncio
import os
from parlant.core.loggers import LogLevel


async def test_azure_logging():
    """Test the Azure OpenAI logging functionality."""

    # Check if Azure environment is configured
    if not os.environ.get("AZURE_ENDPOINT"):
        print("❌ AZURE_ENDPOINT environment variable not set")
        print("Please set AZURE_ENDPOINT to your Azure OpenAI endpoint")
        print("Example: export AZURE_ENDPOINT='https://your-resource.openai.azure.com/'")
        return False

    print("✅ Azure environment configured")
    print(f"Azure Endpoint: {os.environ['AZURE_ENDPOINT']}")

    try:
        # Create server with trace logging enabled
        print("\n🚀 Starting Parlant server with detailed Azure logging...")
        async with p.Server(
            port=8800,
            log_level=LogLevel.TRACE,  # Enable detailed logging
            nlp_service=p.NLPServices.azure,  # Use Azure OpenAI
        ) as server:
            print("✅ Server started successfully!")

            # Create an agent to generate some Azure API calls
            agent = await server.create_agent(
                name="Azure Logging Test Agent",
                description="Agent for testing Azure OpenAI request/response logging",
            )
            print("✅ Agent created successfully!")

            # Create some content that will trigger Azure API calls
            print("\n📝 Creating agent content to trigger Azure API calls...")

            # Create a term (this will trigger embedding API calls)
            await agent.create_term(
                name="API Documentation",
                description="Comprehensive documentation for REST API endpoints including authentication, request/response formats, and error handling",
            )
            print("✅ Term created - embedding API call (no logging)")

            # Create a guideline (this will trigger generation API calls)
            await agent.create_guideline(
                condition="User asks about API endpoints",
                action="Provide detailed information about available endpoints, their parameters, authentication requirements, and example requests",
            )
            print("✅ Guideline created - generation API call logged")

            print("\n🎉 Test completed successfully!")
            print("Check the console output above for detailed Azure request/response logs")
            print("The logs should show:")
            print("  - Request details with TRACE and SPAN IDs for correlation")
            print("  - Response details with matching TRACE and SPAN IDs")
            print("  - Complete prompts and responses for easy debugging")
            print("  - No embedding request/response details (logging disabled)")
            print("\n🔍 Look for patterns like:")
            print("  [TRACE:abc12345] [SPAN:def67890] in both request and response logs")
            print("  This helps correlate parallel LLM calls with their responses")

            return True

    except Exception as e:
        print(f"❌ Error during test: {e}")
        print("\nTroubleshooting tips:")
        print("1. Ensure you're authenticated with Azure (run 'az login' or set AZURE_API_KEY)")
        print("2. Check that your Azure OpenAI resource is accessible")
        print("3. Verify the AZURE_ENDPOINT is correct")
        return False


async def main():
    """Main function to run the test."""
    print("🧪 Testing Azure OpenAI Request/Response Logging")
    print("=" * 60)

    success = await test_azure_logging()

    if success:
        print("\n✅ All tests passed! Azure logging is working correctly.")
        print("\nTo see the detailed logs in action:")
        print("1. Run this script with TRACE logging enabled")
        print("2. Interact with the agent at http://localhost:8800")
        print("3. Watch the console for detailed request/response information")
    else:
        print("\n❌ Tests failed. Please check the error messages above.")


if __name__ == "__main__":
    asyncio.run(main())
