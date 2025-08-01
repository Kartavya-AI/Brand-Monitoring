import os
import requests
import snscrape.modules.twitter as sntwitter
import praw
from datetime import datetime, timedelta
from crewai.tools import tool
from crewai_tools import SerperDevTool

def scrape_linkedin_with_brightdata(query: str) -> str:
    brightdata_api_key = os.getenv("BRIGHTDATA_API_KEY")
    if not brightdata_api_key:
        return "Brightdata API key not found in environment variables."
    
    response = requests.post(
        "https://api.brightdata.com/dca/trigger?collector=c_collector_id",
        headers={"Authorization": f"Bearer {brightdata_api_key}"},
        json={"query": query}
    )
    if response.status_code == 200:
        return f"LinkedIn scraping job for '{query}' started via Brightdata."
    else:
        return f"Failed to start LinkedIn scraping job. Status: {response.status_code}"

def scrape_twitter_with_snscrape(query: str) -> str:
    tweets = []
    try:
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
            if i > 20:
                break
            tweets.append(f"Username: {tweet.user.username}\nTweet: {tweet.rawContent}\nURL: {tweet.url}\n---")
        return "\n".join(tweets) if tweets else "No recent tweets found."
    except Exception as e:
        return f"An error occurred during Twitter scraping: {e}"

def scrape_reddit_with_praw(query: str) -> str:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    if not all([client_id, client_secret, user_agent]):
        return "Reddit API credentials not found in environment variables."

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        subreddit = reddit.subreddit("all")
        posts = []
        for post in subreddit.search(query, limit=5):
            posts.append(f"Title: {post.title}\nSubreddit: r/{post.subreddit}\nURL: {post.url}\n---")
        return "\n".join(posts) if posts else "No relevant Reddit posts found."
    except Exception as e:
        return f"An error occurred during Reddit scraping: {e}"

@tool
def search_internet(query: str) -> str:
    """
    Searches the internet and various social media platforms for a given query to find brand mentions.
    This tool uses SerperDev for general web searches, NewsAPI for news, and specialized functions
    for LinkedIn, X (Twitter), Reddit, and Facebook.
    """
    serper_api_key = os.getenv("SERPER_API_KEY")
    newsapi_key = os.getenv("NEWSAPI_API_KEY")

    if not serper_api_key:
        serper_results = "Serper API key not found in environment variables.\n"
    else:
        try:
            serper_tool = SerperDevTool()
            serper_results = serper_tool.run(query)
        except Exception as e:
            serper_results = f"SerperDev Error: {e}\n"

    if not newsapi_key:
        news_results = "NewsAPI key not found in environment variables.\n"
    else:
        try:
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            news_url = f"https://newsapi.org/v2/everything?q={query}&apiKey={newsapi_key}&language=en&sortBy=publishedAt&from={seven_days_ago}"
            response = requests.get(news_url)
            response.raise_for_status()
            articles = response.json().get("articles", [])
            all_news_results = []
            for article in articles[:5]:
                all_news_results.append(f"Title: {article.get('title', 'N/A')}\nSnippet: {article.get('description', '')}\nSource: {article.get('url', '')}\n---")
            news_results = "\n".join(all_news_results)
        except Exception as e:
            news_results = f"NewsAPI Error: {e}\n"

    linkedin_results = scrape_linkedin_with_brightdata(query)
    twitter_results = scrape_twitter_with_snscrape(query)
    reddit_results = scrape_reddit_with_praw(query)
    facebook_results = scrape_facebook(query)

    combined_results = (
        f"--- General Web Search Results ---\n{serper_results}\n\n"
        f"--- News Search Results ---\n{news_results}\n\n"
        f"--- X (Twitter) Results ---\n{twitter_results}\n\n"
        f"--- Reddit Results ---\n{reddit_results}\n\n"
        f"--- LinkedIn Results ---\n{linkedin_results}\n\n"
        f"--- Facebook Results ---\n{facebook_results}"
    )

    return combined_results