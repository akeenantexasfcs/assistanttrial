#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import openai
import time
import logging
from datetime import datetime
import streamlit as st

# Use Streamlit's secrets management
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Initialize OpenAI client
client = openai.OpenAI()

# Set up logging
logging.basicConfig(level=logging.INFO)

# Constants
MODEL = "GPT-4o-mini"
FILEPATH = "./cryptocurrency.pdf"
THREAD_ID = "thread_F7S14lJmDKPJJKSyKzZ70or4"
ASSIS_ID = "asst_xrWMge210o7NV2yVLrKZaV8B"

def upload_file():
    """Upload a file to OpenAI embeddings"""
    with open(FILEPATH, "rb") as file:
        return client.files.create(file=file, purpose="assistants")

def wait_for_run_completion(thread_id, run_id, sleep_interval=5):
    """Wait for a run to complete and return the response"""
    while True:
        try:
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run.completed_at:
                elapsed_time = run.completed_at - run.created_at
                formatted_elapsed_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
                logging.info(f"Run completed in {formatted_elapsed_time}")
                
                messages = client.beta.threads.messages.list(thread_id=thread_id)
                last_message = messages.data[0]
                response = last_message.content[0].text.value
                return response
        except Exception as e:
            logging.error(f"An error occurred while retrieving the run: {e}")
            return None
        
        logging.info("Waiting for run to complete...")
        time.sleep(sleep_interval)

def main():
    st.title("AI Assistant - Memo Writer")

    # Upload file (you might want to do this only once, not on every run)
    # file_object = upload_file()

    # User input
    user_message = st.text_input("Ask a question about cryptocurrency:", "What is mining?")

    if st.button("Get Answer"):
        with st.spinner("Processing your question..."):
            # Create a message in the thread
            message = client.beta.threads.messages.create(
                thread_id=THREAD_ID,
                role="user",
                content=user_message
            )

            # Run the assistant
            run = client.beta.threads.runs.create(
                thread_id=THREAD_ID,
                assistant_id=ASSIS_ID,
                instructions="Please address the user as Preston"
            )

            # Wait for the run to complete and get the response
            response = wait_for_run_completion(THREAD_ID, run.id)

            if response:
                st.write("Assistant's Response:", response)
            else:
                st.error("Failed to get a response. Please try again.")

        # Optionally, display run steps (for debugging)
        run_steps = client.beta.threads.runs.steps.list(thread_id=THREAD_ID, run_id=run.id)
        st.write("Run Steps:", run_steps.data[0])

if __name__ == "__main__":
    main()

