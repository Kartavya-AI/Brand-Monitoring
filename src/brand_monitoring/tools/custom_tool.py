import os
import requests
import snscrape.modules.twitter as sntwitter
import praw
from datetime import datetime, timedelta
from crewai.tools import tool

# --- SCRAPING FUNCTIONS ---

def scrape_linkedin_with_brightdata(query: str) -> str:
    """Scrapes LinkedIn using the Brightdata service."""
    brightdata_api_key = os.getenv("BRIGHTDATA_API_KEY")
    if not brightdata_api_key:
        return "Warning: Brightdata API key not found. Skipping LinkedIn search."

    try:
        response = requests.post(
            "https://api.brightdata.com/dca/trigger?collector=c_collector_id",
            headers={"Authorization": f"Bearer {brightdata_api_key}"},
            json={"query": query},
            timeout=10
        )
        response.raise_for_status()
        return f"LinkedIn scraping job for '{query}' started successfully via Brightdata."
    except requests.RequestException as e:
        return f"Error: Failed to start LinkedIn scraping job. Status: {e}"

def scrape_twitter_with_snscrape(query: str) -> str:
    """Scrapes Twitter for recent tweets using snscrape."""
    tweets = []
    try:
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
            if i >= 20:
                break
            tweets.append(f"Username: {tweet.user.username}\\nTweet: {tweet.rawContent}\\nURL: {tweet.url}\\n---")
        return "\\n".join(tweets) if tweets else "No recent tweets found."
    except Exception as e:
        return f"Error: Could not scrape Twitter. {e}"

def scrape_reddit_with_praw(query: str) -> str:
    """Scrapes Reddit for recent posts using PRAW."""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")

    if not all([client_id, client_secret, user_agent]):
        return "Warning: Reddit API credentials not found. Skipping Reddit search."

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        subreddit = reddit.subreddit("all")
        submissions = []
        for submission in subreddit.search(query, limit=5):
            submissions.append(f"Title: {submission.title}\\nScore: {submission.score}\\nURL: {submission.url}\\n---")
        return "\\n".join(submissions) if submissions else "No recent Reddit posts found."
    except Exception as e:
        return f"Error: Could not scrape Reddit. {e}"

def scrape_facebook(query: str) -> str:
    """Placeholder for Facebook scraping."""
    return "Info: Facebook scraping is not implemented in this version."

# --- MAIN TOOL ---

@tool("Internet Search Tool")
def search_internet(query: str) -> str:
    """
    Performs a comprehensive search across the web, news, and social media platforms
    to gather brand mentions and relevant information.
    """
    # General Web Search (Serper)
    serper_api_key = os.getenv("SERPER_API_KEY")
    serper_results = ""
    if not serper_api_key:
        serper_results = "Warning: Serper API key not found. Skipping general web search."
    else:
        try:
            payload = {"q": query}
            headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
            response = requests.post("https://google.serper.dev/search", json=payload, timeout=10)
            response.raise_for_status()
            search_data = response.json()
            snippets = []
            for item in search_data.get("organic", [])[:5]:
                snippets.append(f"Title: {item.get('title', 'N/A')}\\nSnippet: {item.get('snippet', '')}\\nSource: {item.get('link', '')}\\n---")
            serper_results = "\\n".join(snippets)
        except Exception as e:
            serper_results = f"Error: Serper API request failed. {e}"


    # News Search (NewsAPI)
    newsapi_key = os.getenv("NEWSAPI_API_KEY")
    news_results = ""
    if not newsapi_key:
        news_results = "Warning: NewsAPI key not found. Skipping news search."
    else:
        try:
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            news_url = f"https://newsapi.org/v2/everything?q={query}&apiKey={newsapi_key}&language=en&sortBy=publishedAt&from={seven_days_ago}"
            response = requests.get(news_url, timeout=10)
            response.raise_for_status()
            articles = response.json().get("articles", [])
            all_news_results = []
            for article in articles[:5]:
                all_news_results.append(f"Title: {article.get('title', 'N/A')}\\nSnippet: {article.get('description', '')}\\nSource: {article.get('url', '')}\\n---")
            news_results = "\\n".join(all_news_results)
        except Exception as e:
            news_results = f"Error: NewsAPI request failed. {e}"

    # Social Media Scraping
    linkedin_results = scrape_linkedin_with_brightdata(query)
    twitter_results = scrape_twitter_with_snscrape(query)
    reddit_results = scrape_reddit_with_praw(query)
    facebook_results = scrape_facebook(query)

    # Combine all results
    combined_results = (
        f"--- General Web Search Results ---\\n{serper_results}\\n\\n"
        f"--- News Search Results ---\\n{news_results}\\n\\n"
        f"--- Twitter Results ---\\n{twitter_results}\\n\\n"
        f"--- Reddit Results ---\\n{reddit_results}\\n\\n"
        f"--- LinkedIn Results ---\\n{linkedin_results}\\n\\n"
        f"--- Facebook Results ---\\n{facebook_results}"
    )

    return combined_results