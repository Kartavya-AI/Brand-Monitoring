import os
from dotenv import load_dotenv
from src.brand_monitoring.crew import BrandMonitoringCrew

load_dotenv()

def run():
    inputs = {
        'company_to_search': 'NVIDIA',
        'keywords_to_search': 'AI chips, RTX 5090, Blackwell architecture, Jensen Huang'
    }

    required_keys = ["GEMINI_API_KEY", "SERPAPI_API_KEY", "NEWSAPI_API_KEY"]
    for key in required_keys:
        if not os.getenv(key):
            print(f"Error: Environment variable {key} is not set.")
            return

    crew_instance = BrandMonitoringCrew()
    result = crew_instance.crew().kickoff(inputs=inputs)
    print("Here is the Final Report:")
    print(result)

if __name__ == "__main__":
    run()