import streamlit as st
import os
from src.brand_monitoring.crew import BrandMonitoringCrew

st.set_page_config(page_title="Brand Monitor", page_icon="📢")

st.title("📢 Brand Monitoring Agent")
st.markdown("This tool uses AI agents to scan the web and generate a brand reputation report.")

st.sidebar.header("Configuration")

gemini_key = st.sidebar.text_input("Enter your Gemini API Key:", type="password")
serper_key = st.sidebar.text_input("Enter your Serper API Key:", type="password")
newsapi_key = st.sidebar.text_input("Enter your NewsAPI API Key:", type="password")

st.sidebar.markdown("""
**Where to get API keys:**
- [Gemini API Key](https://aistudio.google.com/app/apikey)
- [Serper API Key](https://serper.dev/api-key)
- [NewsAPI API Key](https://newsapi.org/account)
""")

company = st.text_input("Enter the Company/Brand Name to Monitor:", placeholder="e.g., Apple")
keywords = st.text_area("Enter Keywords/Topics to Search (comma-separated):", placeholder="e.g., iPhone 17, Vision Pro, WWDC 2026")

if st.button("📊 Generate Report"):
    if not all([gemini_key, serper_key, newsapi_key, company, keywords]):
        st.warning("Please fill in all the fields in the sidebar and main page.")
    else:
        os.environ["GEMINI_API_KEY"] = gemini_key
        os.environ["SERPER_API_KEY"] = serper_key
        os.environ["NEWSAPI_API_KEY"] = newsapi_key

        inputs = {
            'company_to_search': company,
            'keywords_to_search': keywords
        }
        with st.spinner("🤖 The AI Crew is on the job... This may take a few minutes..."):
            try:
                monitoring_crew = BrandMonitoringCrew()
                result = monitoring_crew.crew().kickoff(inputs=inputs)
                st.header("📝 Brand Monitoring Report")
                st.markdown(result)
                if os.path.exists('report.md'):
                    with open('report.md', 'r') as f:
                        report_content = f.read()
                    st.download_button(
                        label="⬇️ Download Report",
                        data=report_content,
                        file_name=f"{company.replace(' ', '_')}_brand_report.md",
                        mime="text/markdown",
                    )
            except Exception as e:
                st.error(f"An error occurred: {e}")