import streamlit as st
import os
import json
import pandas as pd
from dotenv import load_dotenv
from src.brand_monitoring.crew import BrandMonitoringCrew

# Load environment variables from .env file
load_dotenv()

st.set_page_config(page_title="Brand Monitor", page_icon="🕵️")

st.title("🕵️ Brand Monitoring Agent")
st.markdown("This tool uses AI agents to scan the web and generate a brand reputation report based on your inputs.")

# --- Sidebar for API Key Configuration ---
with st.sidebar:
    st.header("Configuration")
    st.markdown("Enter your Gemini API key. The other required keys will be loaded from your `.env` file.")
    
    gemini_key = st.text_input(
        "Enter your Gemini API Key:", 
        type="password", 
        help="You can get your Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)."
    )
    st.markdown("---")
    st.info("Ensure your `.env` file in the project root contains `SERPER_API_KEY` and `NEWSAPI_API_KEY`.")


# --- Main Application ---
st.header("Monitoring Inputs")
company = st.text_input("Enter the Company/Brand Name to Monitor:", placeholder="e.g., OpenAI")
keywords = st.text_area("Enter Keywords/Topics to Search (comma-separated):", placeholder="e.g., Sora, GPT-5, Sam Altman", height=100)

if st.button("🚀 Generate Report"):
    # Validate user inputs
    if not gemini_key:
        st.warning("Please enter your Gemini API Key in the sidebar.")
    elif not company or not keywords:
        st.warning("Please enter the Company Name and Keywords to monitor.")
    # Validate that keys are loaded from .env
    elif not os.getenv("SERPER_API_KEY") or not os.getenv("NEWSAPI_API_KEY"):
        st.error("API Key Error: Make sure `SERPER_API_KEY` and `NEWSAPI_API_KEY` are set in your .env file.")
    else:
        # Set environment variable for Gemini API key for the current run
        os.environ["GEMINI_API_KEY"] = gemini_key

        inputs = {
            'company_to_search': company,
            'keywords_to_search': keywords
        }

        with st.spinner("🤖 The AI Crew is on the job... This may take a few minutes..."):
            try:
                monitoring_crew = BrandMonitoringCrew()
                # Kickoff the crew. It now returns a CrewOutput object.
                crew_output = monitoring_crew.crew().kickoff(inputs=inputs)
                
                # The raw JSON string is in the .raw attribute of the output
                crew_result_json_str = crew_output.raw
                
                # Parse the JSON string into a Python dictionary
                crew_result_dict = json.loads(crew_result_json_str)

                # --- Display the Report ---
                st.header("📊 Brand Monitoring Report")

                # Extract and display the markdown report
                report_markdown = crew_result_dict.get('report_markdown', '### Report could not be generated.')
                st.markdown(report_markdown)

                # Extract chart data for visualization
                chart_data = crew_result_dict.get('chart_data', {})
                sentiment_data = chart_data.get('sentiment', {})

                if sentiment_data:
                    st.subheader("Sentiment Analysis Breakdown")
                    # Convert sentiment data to a pandas DataFrame for charting
                    df = pd.DataFrame(list(sentiment_data.items()), columns=['Sentiment', 'Percentage'])
                    st.bar_chart(df.set_index('Sentiment'))

                # --- Download Button ---
                st.download_button(
                    label="💾 Download Report as Markdown",
                    data=report_markdown,
                    file_name=f"{company.replace(' ', '_').lower()}_brand_report.md",
                    mime="text/markdown",
                )

            except json.JSONDecodeError:
                st.error("Error: The AI crew returned a malformed response. Could not parse the report.")
                # Show the raw output for debugging
                st.code(crew_result_json_str) 
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                # If the error is not JSON related, show the full output object
                st.write("Full crew output for debugging:")
                st.write(crew_output)

