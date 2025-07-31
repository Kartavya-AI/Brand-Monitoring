import os
import requests
from crewai.tools import tool
from crewai_tools import SerperDevTool

@tool
def search_internet(query: str) -> str:
    """
    Searches the internet and news sources for a given query to find brand mentions.
    This tool uses SerperDev for general web searches and NewsAPI for dedicated news searches.
    """
    try:
        if not os.getenv("SERPER_API_KEY"):
            raise ValueError("SERPER_API_KEY environment variable not set.")
        serper_tool = SerperDevTool()
        serper_results = serper_tool.run(query)
    except Exception as e:
        serper_results = f"SerperDev Error: {e}\n"

    all_news_results = []
    try:
        newsapi_key = os.getenv("NEWSAPI_API_KEY")
        if not newsapi_key:
            raise ValueError("NEWSAPI_API_KEY environment variable not set.")

        news_url = f"https://newsapi.org/v2/everything?q={query}&apiKey={newsapi_key}&language=en&sortBy=publishedAt"
        response = requests.get(news_url)
        response.raise_for_status()
        articles = response.json().get("articles", [])

        for article in articles[:5]:
            if "description" in article and "url" in article:
                all_news_results.append(f"Title: {article.get('title', 'N/A')}\nSnippet: {article['description']}\nSource: {article['url']}\n---")

        news_results = "\n".join(all_news_results)

    except Exception as e:
        news_results = f"NewsAPI Error: {e}\n"

    combined_results = f"--- General Web Search Results ---\n{serper_results}\n\n--- News Search Results ---\n{news_results}"

    if "Error" in serper_results and "Error" in news_results:
        return "No results found from any tool. Check your query or API keys."

    return combined_results