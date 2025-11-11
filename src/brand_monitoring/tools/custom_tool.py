import os
import requests
import snscrape.modules.twitter as sntwitter
import asyncpraw
from datetime import datetime, timedelta
from crewai.tools import tool
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ENHANCED SCRAPING FUNCTIONS ---

def scrape_linkedin_with_brightdata(query: str) -> str:
    """Scrapes LinkedIn using the Brightdata service with improved error handling."""
    brightdata_api_key = os.getenv("BRIGHTDATA_API_KEY")
    if not brightdata_api_key:
        return "Warning: Brightdata API key not found. Skipping LinkedIn search."

    try:
        response = requests.post(
            "https://api.brightdata.com/dca/trigger?collector=c_collector_id",
            headers={"Authorization": f"Bearer {brightdata_api_key}"},
            json={"query": query},
            timeout=15
        )
        response.raise_for_status()
        return f"LinkedIn scraping job for '{query}' started successfully via Brightdata."
    except requests.exceptions.Timeout:
        return "Warning: LinkedIn scraping timed out. Service may be slow."
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            return "Warning: LinkedIn API rate limit reached. Try again later."
        return f"Warning: LinkedIn API error (Status {e.response.status_code}). Skipping."
    except requests.RequestException as e:
        return f"Warning: LinkedIn scraping failed - {str(e)[:100]}. Skipping."

def scrape_twitter_with_snscrape(query: str) -> str:
    """Scrapes Twitter for recent tweets using snscrape with fallback."""
    tweets = []
    try:
        search_query = f"{query} since:{(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')}"
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(search_query).get_items()):
            if i >= 15:  # Reduced limit for reliability
                break
            tweets.append(f"Username: @{tweet.user.username}\nTweet: {tweet.rawContent[:200]}...\nURL: {tweet.url}\n---")
        
        if tweets:
            return "\n".join(tweets)
        else:
            return f"No recent tweets found for '{query}'. This may be due to API limitations or search restrictions."
            
    except Exception as e:
        logger.warning(f"Twitter scraping failed: {e}")
        return f"Warning: Twitter scraping unavailable - {str(e)[:100]}. This is common due to API restrictions."

def scrape_reddit_with_praw(query: str) -> str:
    """Scrapes Reddit for recent posts using PRAW with proper URL formatting."""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "brand-monitoring-app v1.0")

    if not all([client_id, client_secret]):
        return "Warning: Reddit API credentials not found. Skipping Reddit search."

    try:
        reddit = asyncpraw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            timeout=10
        )
        
        # Test connection
        reddit.auth.limits
        
        submissions = []
        subreddit = reddit.subreddit("all")
        
        for submission in subreddit.search(query, limit=10, time_filter='week'):
            # Create proper Reddit URL
            reddit_url = f"https://www.reddit.com{submission.permalink}"
            
            submissions.append(
                f"Platform: Reddit (r/{submission.subreddit.display_name})\n"
                f"Title: {submission.title[:150]}...\n"
                f"Score: {submission.score} | Comments: {submission.num_comments}\n"
                f"URL: {reddit_url}\n---"
            )
            
            if len(submissions) >= 8:
                break
                
        if submissions:
            return "\n".join(submissions)
        else:
            return f"No recent Reddit posts found for '{query}'."
            
    except Exception as e:
        logger.error(f"Reddit API error: {e}")
        return f"Warning: Reddit search failed - {str(e)[:100]}."

def scrape_facebook(query: str) -> str:
    """Enhanced placeholder for Facebook scraping with explanation."""
    return (
        "Info: Facebook scraping requires special permissions and is not implemented. "
        "For Facebook monitoring, consider using Facebook's official Graph API with proper business verification."
    )

def enhanced_web_search(query: str, serper_api_key: str) -> str:
    """Enhanced web search with proper URL extraction."""
    search_results = []
    
    try:
        payload = {
            "q": query,
            "num": 8,
            "gl": "us",
            "hl": "en"
        }
        headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
        response = requests.post("https://google.serper.dev/search", 
                               json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        search_data = response.json()
        logger.info(f"Serper response keys: {search_data.keys()}")
        
        # Extract organic results with proper URLs
        for item in search_data.get("organic", []):
            title = item.get('title', 'N/A')
            snippet = item.get('snippet', 'No description available')
            link = item.get('link', '')
            
            # Validate URL format
            if link and (link.startswith('http://') or link.startswith('https://')):
                search_results.append(
                    f"Platform: Web Search\n"
                    f"Title: {title}\n"
                    f"Snippet: {snippet[:200]}...\n"
                    f"URL: {link}\n---"
                )
        
        # Also check news results if available
        for item in search_data.get("news", []):
            title = item.get('title', 'N/A')
            snippet = item.get('snippet', 'No description available')
            link = item.get('link', '')
            
            if link and (link.startswith('http://') or link.startswith('https://')):
                search_results.append(
                    f"Platform: News\n"
                    f"Title: {title}\n"
                    f"Snippet: {snippet[:200]}...\n"
                    f"URL: {link}\n---"
                )
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            return "Warning: Search API rate limit reached."
        return f"Warning: Search API error (Status {e.response.status_code})."
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"Warning: Web search failed - {str(e)[:100]}."
    
    return "\n".join(search_results) if search_results else f"No web results found for '{query}'."

# --- MAIN TOOL ---

@tool("Internet Search Tool")
def search_internet(query: str) -> str:
    """
    Performs a comprehensive search across the web, news, and social media platforms
    to gather brand mentions and relevant information with enhanced error handling.
    """
    results_sections = []
    
    # General Web Search (Serper)
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key:
        serper_results = "Warning: Serper API key not found. Skipping general web search."
    else:
        serper_results = enhanced_web_search(query, serper_api_key)
    
    results_sections.append(f"--- General Web Search Results ---\n{serper_results}\n")

    newsapi_key = os.getenv("NEWSAPI_API_KEY")
    if not newsapi_key:
        news_results = "Warning: NewsAPI key not found. Skipping news search."
    else:
        try:
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            news_url = (
                f"https://newsapi.org/v2/everything?q={query}&apiKey={newsapi_key}"
                f"&language=en&sortBy=publishedAt&from={seven_days_ago}&pageSize=8"
            )
            response = requests.get(news_url, timeout=15)
            response.raise_for_status()
            
            articles = response.json().get("articles", [])
            if articles:
                news_items = []
                for article in articles:
                    title = article.get('title', '')
                    description = article.get('description', 'No description')
                    url = article.get('url', '')
                    source_name = article.get('source', {}).get('name', 'Unknown')
                    
                    # Skip removed articles and validate URLs
                    if (title and title != '[Removed]' and 
                        url and (url.startswith('http://') or url.startswith('https://'))):
                        news_items.append(
                            f"Platform: News ({source_name})\n"
                            f"Title: {title}\n"
                            f"Description: {description[:200]}...\n"
                            f"URL: {url}\n---"
                        )
                        
                news_results = "\n".join(news_items) if news_items else f"No recent news articles found for '{query}'."
            else:
                news_results = f"No recent news articles found for '{query}'."
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 426:
                news_results = "Warning: NewsAPI requires upgrade for this request."
            else:
                news_results = f"Warning: News search failed (Status {e.response.status_code})."
        except Exception as e:
            news_results = f"Warning: NewsAPI request failed - {str(e)[:100]}."

    results_sections.append(f"--- News Search Results ---\n{news_results}\n")

    twitter_results = scrape_twitter_with_snscrape(query)
    reddit_results = scrape_reddit_with_praw(query)
    linkedin_results = scrape_linkedin_with_brightdata(query)
    facebook_results = scrape_facebook(query)

    results_sections.extend([
        f"--- Twitter Results ---\n{twitter_results}\n",
        f"--- Reddit Results ---\n{reddit_results}\n",
        f"--- LinkedIn Results ---\n{linkedin_results}\n",
        f"--- Facebook Results ---\n{facebook_results}"
    ])

    combined_results = "\n".join(results_sections)
    
    # Add search summary
    summary = (
        f"\n--- Search Summary ---\n"
        f"Search completed for: '{query}'\n"
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Note: Some platforms may have limited results due to API restrictions or company visibility.\n"
    )
    
    return combined_results + summary
