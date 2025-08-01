from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
from src.brand_monitoring.crew import BrandMonitoringCrew

app = FastAPI(
    title="Brand Monitoring API",
    description="An API to trigger a CrewAI-powered brand monitoring agent.",
    version="1.1.0"
)

class MonitoringRequest(BaseModel):
    company_to_search: str
    keywords_to_search: str
    gemini_api_key: str

@app.post("/monitor", summary="Start a new brand monitoring task")
def run_monitoring_crew(request: MonitoringRequest):
    os.environ["GEMINI_API_KEY"] = request.gemini_api_key
    required_keys = ["SERPER_API_KEY", "NEWSAPI_API_KEY"]
    for key in required_keys:
        if not os.getenv(key):
            raise HTTPException(
                status_code=500,
                detail=f"Server configuration error: Environment variable {key} is not set."
            )

    inputs = {
        'company_to_search': request.company_to_search,
        'keywords_to_search': request.keywords_to_search
    }

    try:
        crew_instance = BrandMonitoringCrew()
        crew_result_json_str = crew_instance.crew().kickoff(inputs=inputs)
        crew_result_dict = json.loads(crew_result_json_str)
        return {"status": "success", "data": crew_result_dict}

    except json.JSONDecodeError:
         raise HTTPException(
            status_code=500,
            detail="Error decoding the JSON response from the AI crew."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while running the crew: {str(e)}"
        )

@app.get("/", summary="Health Check")
def read_root():
    return {"status": "API is running"}