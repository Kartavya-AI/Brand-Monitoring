import os
from crewai import Agent, Task, Crew, Process, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agent import Agent
from langchain_google_genai import ChatGoogleGenerativeAI

from src.brand_monitoring.tools.custom_tool import search_internet

@CrewBase
class BrandMonitoringCrew():
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self) -> None:
        self.gemini_llm = LLM(
            model='gemini/gemini-2.0-flash-001',
            api_key=os.environ.get("GEMINI_API_KEY"),
            temperature=0.0
        )

    @agent
    def collector(self) -> Agent:
        return Agent(
            config=self.agents_config['collector'],
            tools=[search_internet],
            llm=self.gemini_llm,
            verbose=True
        )

    @agent
    def analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['analyst'],
            llm=self.gemini_llm,
            verbose=True
        )

    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config['writer'],
            llm=self.gemini_llm,
            verbose=True
        )

    @task
    def collect_mentions_task(self) -> Task:
        return Task(
            config=self.tasks_config['collect_mentions_task'],
            agent=self.collector()
        )

    @task
    def analyze_mentions_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_mentions_task'],
            agent=self.analyst(),
            context=[self.collect_mentions_task()]
        )

    @task
    def generate_report_task(self) -> Task:
        return Task(
            config=self.tasks_config['generate_report_task'],
            agent=self.writer(),
            context=[self.analyze_mentions_task()]
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )