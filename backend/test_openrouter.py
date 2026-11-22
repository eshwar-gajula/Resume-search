"""Quick test for Cerebras integration"""
import asyncio
import json
import time
import traceback
from app.services.llm_provider import LLMProvider


async def main():
    llm = LLMProvider()
    print(f"Model: {llm.model}")
    print(f"Base URL: {llm.base_url}")
    print(f"API key configured: {'yes' if llm.api_key else 'no'}")
    print()

    # Test 1: Simple chat
    print("=" * 50)
    print("TEST 1: Simple chat")
    print("=" * 50)
    try:
        start = time.time()
        result = await llm.chat(
            [{"role": "user", "content": "Say hello in one sentence. Be brief."}],
            max_tokens=100,
        )
        elapsed = time.time() - start
        print(f"Time: {elapsed:.2f}s")
        print(f"Response: {result}")
        print("PASS!" if len(result) > 0 else "FAIL - empty!")
    except Exception as e:
        print(f"FAIL: {e}")
        traceback.print_exc()

    print()

    # Test 2: Resume parsing (JSON)
    print("=" * 50)
    print("TEST 2: Resume parsing (JSON mode)")
    print("=" * 50)
    try:
        start = time.time()
        parsed = await llm.parse_resume(
            "John Smith\njohn@email.com\n+1-555-1234\n\n"
            "Skills: Python, FastAPI, Docker, React\n\n"
            "Experience:\nSenior Developer at Acme Corp, 2022-Present\n"
            "Built microservices with FastAPI and Docker\n\n"
            "Education:\nB.Tech Computer Science, MIT, 2019\n\n"
            "GitHub: github.com/johnsmith"
        )
        elapsed = time.time() - start
        print(f"Time: {elapsed:.2f}s")
        if "error" in parsed:
            print(f"ERROR: {parsed['error']}")
            if "raw" in parsed:
                print(f"Raw: {parsed['raw'][:300]}")
        else:
            print(json.dumps(parsed, indent=2)[:800])
            print("\nPASS!")
    except Exception as e:
        print(f"FAIL: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
