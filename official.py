#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import openai
import time
import logging
from datetime import datetime
import streamlit as st
import boto3
from botocore.exceptions import NoCredentialsError
from io import BytesIO

# Use Streamlit's secrets management
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Initialize OpenAI client
client = openai.OpenAI()

# Initialize boto3 session with credentials from secrets.toml
session = boto3.Session(
    aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
    aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
    region_name=st.secrets["aws"]["region_name"]
)

# Create AWS clients
s3 = session.client('s3')
textract = session.client('textract')

# Set up logging
logging.basicConfig(level=logging.INFO)

# Constants
MODEL = "GPT-4o-mini"
THREAD_ID = "thread_F7S14lJmDKPJJKSyKzZ70or4"
ASSIS_ID = "asst_xrWMge210o7NV2yVLrKZaV8B"

# Assistant Role Description
ASSISTANT_ROLE_DESCRIPTION = """
You are an expert Credit Analyst AI assistant specialized in writing indication of interest memos for the Executive Loan Committee. Your primary function is to help decide whether to participate in loan offerings. You should have Action Required with a date and time of response being needed. Unless that is supplied to you, use a placeholder.

Key Responsibilities:
- Write clear, concise memos ranging from 250 to 1,000 words, depending on deal complexity.
- Use bullet points for clarity.
- Provide insights on loan ratings and their implications.

Loan Rating Guidelines:
- **Probability of Default (PD):**
  - PD7 or less: Viewed positively.
  - PD8: Generally neutral.
  - PD9 or higher: Viewed negatively.
  
- **Loss Given Default (LGD):**
  - Preferred ratings: B or D.
  - Other ratings: Less favorable.

Memo Structure:
- **Section 0: Introduction**
  - Provide deal details.
  - Include optional Strengths and Drawbacks.
  - Indicate your disposition (Positive, Negative, or Neutral).

- **Section 1: Borrower Overview and Deal Summary**
  - Research borrower using provided documents and/or internet sources.
  - Summarize key points about the borrower and the deal.

- **Section 2: Pricing**
  - Analyze Income Yield and Capital Yield data.
  - Evaluate spreads:
    - Above 2.5%: Very favorable (considering PD).
    - Around 2.0%: Neutral.
    - Below 2.0%: Less favorable.
    - Below 1.50%: Undesirable (unless very low PD).

- **Section 3: Financial Analysis**
  - Provide "back of the envelope" financial analysis using uploaded files.
  - Include relevant information such as:
    - Debt/EBITDA tables for publicly traded proxies.
    - Capitalization tables.
    - Historical performance data.

- **Section 4: Appendix**
  - Include any additional helpful information about the credit.
"""

# Function to upload file to S3
def upload_to_s3(fileobj, bucket_name, object_name):
    try:
        s3.upload_fileobj(fileobj, bucket_name, object_name)
        print(f"File uploaded to {bucket_name}/{object_name}")
    except NoCredentialsError:
        print("AWS credentials not available.")

# Function to start Textract job
def start_text_detection(bucket_name, object_name):
    response = textract.start_document_text_detection(
        DocumentLocation={
            'S3Object': {
                'Bucket': bucket_name,
                'Name': object_name
            }
        }
    )
    return response['JobId']

# Function to check if the Textract job is complete
def is_job_complete(job_id):
    response = textract.get_document_text_detection(JobId=job_id)
    status = response['JobStatus']
    return status

# Function to retrieve and parse the Textract response
def get_text_from_response(job_id):
    response = textract.get_document_text_detection(JobId=job_id)
    blocks = response['Blocks']
    text = ''
    
    # Handle pagination
    next_token = response.get('NextToken')
    while next_token:
        response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
        blocks.extend(response['Blocks'])
        next_token = response.get('NextToken')
    
    for block in blocks:
        if block['BlockType'] == 'LINE':
            text += block['Text'] + '\n'
    return text

# Password check function
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

# Main function
def main():
    st.title("AI Assistant - Memo Writer")

    if not check_password():
        st.stop()

    bucket_name = st.secrets["aws"]["s3_bucket_name"]

    if 'job_ids' not in st.session_state:
        st.session_state['job_ids'] = {}
    if 'document_texts' not in st.session_state:
        st.session_state['document_texts'] = {}

    # Slot 1 Document Upload and Text Extraction
    st.subheader("Slot 1 [Suggested Upload = Marketing Materials]")
    uploaded_file1 = st.file_uploader("Upload a document for Slot 1", type=['pdf', 'docx', 'png', 'jpg'], key="slot1")

    if uploaded_file1 and 'slot1' not in st.session_state.document_texts:
        object_name1 = uploaded_file1.name
        upload_to_s3(uploaded_file1, bucket_name, object_name1)
        job_id1 = start_text_detection(bucket_name, object_name1)
        st.session_state.job_ids['slot1'] = job_id1
        st.session_state['slot1_object_name'] = object_name1
        st.info("Slot 1: Extracting text...")

    if 'slot1' in st.session_state.job_ids:
        job_id1 = st.session_state.job_ids['slot1']
        status = is_job_complete(job_id1)
        if status == 'SUCCEEDED':
            document_text1 = get_text_from_response(job_id1)
            st.session_state.document_texts['slot1'] = document_text1
            st.success("Slot 1: Text extracted successfully.")
        elif status == 'FAILED':
            st.error("Slot 1: Failed to extract text.")

    # Similarly handle Slot 2 and Slot 3...

    if st.button("Generate Memo"):
        additional_context = ""
        if 'slot1' in st.session_state.document_texts:
            additional_context += f"\n\n[Marketing Materials]:\n{st.session_state.document_texts['slot1']}"
        if 'slot2' in st.session_state.document_texts:
            additional_context += f"\n\n[Term Sheet]:\n{st.session_state.document_texts['slot2']}"
        if 'slot3' in st.session_state.document_texts:
            additional_context += f"\n\n[Pricing Data]:\n{st.session_state.document_texts['slot3']}"

        user_message = st.text_input("Enter any additional instructions or information:", "")

        prompt = f"""
{ASSISTANT_ROLE_DESCRIPTION}

Please write an indication of interest memo based on the provided documents and data.

{additional_context}

{user_message}
"""
        message = client.beta.threads.messages.create(thread_id=THREAD_ID, role="user", content=prompt)
        run = client.beta.threads.runs.create(thread_id=THREAD_ID, assistant_id=ASSIS_ID, instructions="Generate memo.")
        
        response = wait_for_run_completion(THREAD_ID, run.id)
        if response:
            st.write("**Generated Memo:**")
            st.write(response)

# Function to wait for the run to complete
def wait_for_run_completion(thread_id, run_id, sleep_interval=5):
    while True:
        try:
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run.completed_at:
                elapsed_time = run.completed_at - run.created_at
                logging.info(f"Run completed in {elapsed_time}")
                messages = client.beta.threads.messages.list(thread_id=thread_id)
                last_message = messages.data[0]
                response = last_message.content[0].text.value
                return response
        except Exception as e:
            logging.error(f"Error: {e}")
            return None
        time.sleep(sleep_interval)

if __name__ == "__main__":
    main()

