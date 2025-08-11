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

with st.sidebar:
    st.header("🔑 API Configuration")
    st.info("Enter your API keys below. If a key is in your `.env` file, it will be used as a default.")
    def get_api_key(key_name, help_url):
        return st.text_input(
            f"{key_name.replace('_', ' ').title()}:",
            type="password",
            value=os.getenv(key_name, ""),
            help=f"Get your key from {help_url}"
        )

    gemini_key = get_api_key("GEMINI_API_KEY", "[Google AI Studio](https://aistudio.google.com/app/apikey)")
    serper_key = get_api_key("SERPER_API_KEY", "[Serper](https://serper.dev/)")
    newsapi_key = get_api_key("NEWSAPI_API_KEY", "[NewsAPI](https://newsapi.org/)")
    brightdata_key = get_api_key("BRIGHTDATA_API_KEY", "[Brightdata](https://brightdata.com/)")
    st.markdown("---")
    st.subheader("Reddit API Credentials")
    reddit_client_id = get_api_key("REDDIT_CLIENT_ID", "[Reddit Apps](https://www.reddit.com/prefs/apps)")
    reddit_client_secret = get_api_key("REDDIT_CLIENT_SECRET", "[Reddit Apps](https://www.reddit.com/prefs/apps)")
    reddit_user_agent = st.text_input("Reddit User Agent:", value=os.getenv("REDDIT_USER_AGENT", "brand-monitoring by /u/your_username"), help="A unique user agent for the Reddit API.")

st.header("📊 Monitoring Inputs")

company = st.text_input("Enter the Company/Brand Name:", placeholder="e.g., Vercel")
keywords = st.text_area("Enter Keywords/Topics (comma-separated):", placeholder="e.g., Next.js, AI, hosting", height=100)


if st.button("🚀 Generate Report"):
    if not all([gemini_key, serper_key, newsapi_key, company, keywords]):
        st.warning("Please provide all required API Keys, a Company Name, and Keywords.")
    else:
        os.environ["GEMINI_API_KEY"] = gemini_key
        os.environ["SERPER_API_KEY"] = serper_key
        os.environ["NEWSAPI_API_KEY"] = newsapi_key
        os.environ["BRIGHTDATA_API_KEY"] = brightdata_key
        os.environ["REDDIT_CLIENT_ID"] = reddit_client_id
        os.environ["REDDIT_CLIENT_SECRET"] = reddit_client_secret
        os.environ["REDDIT_USER_AGENT"] = reddit_user_agent
        inputs = {
            'company_to_search': company,
            'keywords_to_search': keywords
        }
        with st.spinner("🤖 The AI Crew is on the job... This might take a few minutes..."):
            try:
                monitoring_crew = BrandMonitoringCrew()
                crew_output = monitoring_crew.crew().kickoff(inputs=inputs)

                st.header("📈 Brand Monitoring Report")
                crew_result_dict = json.loads(crew_output.raw)

                report_markdown = crew_result_dict.get('report_markdown', '### Report could not be generated.')
                st.markdown(report_markdown)
                chart_data = crew_result_dict.get('chart_data', {})
                sentiment_data = chart_data.get('sentiment', {})

                if sentiment_data:
                    st.subheader("Sentiment Analysis Breakdown")
                    df = pd.DataFrame(list(sentiment_data.items()), columns=['Sentiment', 'Percentage'])
                    st.bar_chart(df.set_index('Sentiment'))

                st.download_button(
                    label="💾 Download Report",
                    data=report_markdown,
                    file_name=f"{company.replace(' ', '_').lower()}_brand_report.md",
                    mime="text/markdown",
                )

                with st.expander("Show Raw JSON Output"):
                    st.json(crew_result_dict)


            except json.JSONDecodeError as e:
                st.error(f"Error: Failed to parse the AI crew's JSON response. This may be due to an API error or an unexpected output format.")
                st.code(crew_output.raw)
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                st.error("Please check your API keys and internet connection. If the problem persists, the external services may be down.")