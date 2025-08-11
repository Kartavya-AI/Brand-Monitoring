import streamlit as st
import os
import json
import pandas as pd
from dotenv import load_dotenv
from src.brand_monitoring.crew import BrandMonitoringCrew

load_dotenv()

st.set_page_config(page_title="Brand Monitor", page_icon="🕵️", layout="wide")

st.title("🕵️ Brand Monitoring Agent")
st.markdown("This tool uses AI agents to scan the web and generate a brand reputation report based on your inputs.")

def validate_company_name(company):
    if len(company.strip()) < 2:
        return False, "Company name must be at least 2 characters long."
    if company.strip().isdigit():
        return False, "Company name cannot be only numbers."
    return True, ""

with st.sidebar:
    st.header("🔑 API Configuration")
    st.info("Enter your API keys below. At minimum, you need Gemini and Serper keys.")
    def get_api_key(key_name, help_url, required=False):
        label = f"{key_name.replace('_', ' ').title()}:"
        if required:
            label += " *"
        return st.text_input(
            label,
            type="password",
            value=os.getenv(key_name, ""),
            help=f"Get your key from {help_url}"
        )

    gemini_key = get_api_key("GEMINI_API_KEY", "[Google AI Studio](https://aistudio.google.com/app/apikey)", required=True)
    serper_key = get_api_key("SERPER_API_KEY", "[Serper](https://serper.dev/)", required=True)
    newsapi_key = get_api_key("NEWSAPI_API_KEY", "[NewsAPI](https://newsapi.org/)")
    brightdata_key = get_api_key("BRIGHTDATA_API_KEY", "[Brightdata](https://brightdata.com/)")
    
    st.markdown("---")
    st.subheader("Reddit API Credentials (Optional)")
    reddit_client_id = get_api_key("REDDIT_CLIENT_ID", "[Reddit Apps](https://www.reddit.com/prefs/apps)")
    reddit_client_secret = get_api_key("REDDIT_CLIENT_SECRET", "[Reddit Apps](https://www.reddit.com/prefs/apps)")
    reddit_user_agent = st.text_input("Reddit User Agent:", 
                                     value=os.getenv("REDDIT_USER_AGENT", "brand-monitoring by /u/your_username"), 
                                     help="A unique user agent for the Reddit API.")

st.header("📊 Monitoring Inputs")

company = st.text_input("Enter the Company/Brand Name: *", placeholder="e.g., Vercel, OpenAI, Tesla")
keywords = st.text_area("Enter Keywords/Topics (comma-separated):", 
                       placeholder="e.g., Next.js, AI, hosting, customer service", 
                       height=100,
                       help="Include product names, CEO names, or specific topics related to the brand")

st.caption("💡 Works best with well-known companies that have online presence. Examples: Tesla, OpenAI, Vercel, Stripe, etc.")

if st.button("🚀 Generate Report"):
    if not all([gemini_key, serper_key]):
        st.error("❌ Gemini API Key and Serper API Key are required to generate reports.")
    elif not company.strip():
        st.error("❌ Please enter a company/brand name.")
    else:
        is_valid, validation_msg = validate_company_name(company)
        if not is_valid:
            st.error(f"❌ {validation_msg}")
        else:
            os.environ["GEMINI_API_KEY"] = gemini_key
            os.environ["SERPER_API_KEY"] = serper_key
            if newsapi_key:
                os.environ["NEWSAPI_API_KEY"] = newsapi_key
            if brightdata_key:
                os.environ["BRIGHTDATA_API_KEY"] = brightdata_key
            if reddit_client_id and reddit_client_secret:
                os.environ["REDDIT_CLIENT_ID"] = reddit_client_id
                os.environ["REDDIT_CLIENT_SECRET"] = reddit_client_secret
                os.environ["REDDIT_USER_AGENT"] = reddit_user_agent 
            search_keywords = keywords.strip() if keywords.strip() else f"{company} reviews, news, mentions"
            
            inputs = {
                'company_to_search': company.strip(),
                'keywords_to_search': search_keywords
            }
            
            with st.spinner("🤖 The AI Crew is searching across the web... This may take 2-5 minutes..."):
                try:
                    monitoring_crew = BrandMonitoringCrew()
                    crew_output = monitoring_crew.crew().kickoff(inputs=inputs)

                    st.header("📈 Brand Monitoring Report")
                    try:
                        crew_result_dict = json.loads(crew_output.raw)
                    except json.JSONDecodeError:
                        import re
                        json_match = re.search(r'\{.*\}', crew_output.raw, re.DOTALL)
                        if json_match:
                            crew_result_dict = json.loads(json_match.group())
                        else:
                            raise json.JSONDecodeError("No valid JSON found", crew_output.raw, 0)

                    report_markdown = crew_result_dict.get('report_markdown', '### Report could not be generated.')
                    st.markdown(report_markdown)
                    chart_data = crew_result_dict.get('chart_data', {})
                    sentiment_data = chart_data.get('sentiment', {})

                    if sentiment_data and any(sentiment_data.values()):
                        st.subheader("Sentiment Analysis Breakdown")
                        df = pd.DataFrame(list(sentiment_data.items()), columns=['Sentiment', 'Percentage'])
                        st.bar_chart(df.set_index('Sentiment'))
                    else:
                        st.info("📊 No sentiment data available for visualization.")
                    st.download_button(
                        label="💾 Download Report",
                        data=report_markdown,
                        file_name=f"{company.replace(' ', '_').lower()}_brand_report_{pd.Timestamp.now().strftime('%Y%m%d')}.md",
                        mime="text/markdown",
                    )
                    with st.expander("Show Raw JSON Output"):
                        st.json(crew_result_dict)

                except json.JSONDecodeError as e:
                    st.error("❌ Failed to parse the AI response. This may indicate an API issue or unexpected output format.")
                    st.code(str(crew_output.raw)[:1000] + "..." if len(str(crew_output.raw)) > 1000 else str(crew_output.raw))
                    st.info("💡 Try again in a few minutes. If the problem persists, check your API keys or try a different company name.")
                    
                except Exception as e:
                    st.error(f"❌ An error occurred: {str(e)}")
                    st.info("💡 Possible causes:\n- API rate limits reached\n- Network connectivity issues\n- Invalid API keys\n- Company name too obscure or new")
                    st.info("🔧 Solutions:\n- Wait a few minutes and try again\n- Try a more well-known company\n- Check your API keys\n- Ensure stable internet connection")

st.markdown("---")
st.markdown("**💡 Tips for better results:**")
st.markdown("- Use well-known company names")
st.markdown("- Include specific product names or CEO names in keywords")
st.markdown("- Ensure stable internet connection")
st.markdown("- Wait between requests to avoid rate limits")