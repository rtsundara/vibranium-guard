import asyncio
import json
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agent import app

async def run_all_logs():
    runner = InMemoryRunner(app=app)
    
    print("Starting DLP Workflow execution on proxy_logs.csv...")
    for i in range(14):
        print(f"\n--- Processing Log Index {i} ---")
        session = await runner.session_service.create_session(
            app_name="app", user_id="test_user"
        )
        
        # We send the index as a JSON string matching the parser
        input_data = json.dumps({"index": i})
        content = types.Content(role="user", parts=[types.Part.from_text(text=input_data)])
        
        try:
            async for event in runner.run_async(
                user_id="test_user",
                session_id=session.id,
                new_message=content,
            ):
                if hasattr(event, "message") and event.message and hasattr(event.message, "parts") and event.message.parts:
                    text = event.message.parts[0].text
                    if text and text.strip().startswith("{") and '"audit_decision"' in text:
                        try:
                            result_dict = json.loads(text.strip())
                            print("FINAL AUDIT RESULT:", json.dumps(result_dict, indent=2))
                        except Exception:
                            pass
        except Exception as e:
            print(f"Error processing index {i}: {e}")
            
        # Add a delay to avoid hitting the 15 RPM free tier rate limit
        await asyncio.sleep(4)

if __name__ == "__main__":
    asyncio.run(run_all_logs())
