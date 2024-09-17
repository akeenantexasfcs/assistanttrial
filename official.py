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
  - Use judgment to determine relevant content.

Additional Notes:

- Reference provided sample memos for structural inspiration.
- Adapt your analysis based on the complexity and specifics of each deal.
- Your ultimate goal is to facilitate a deeper understanding of complex loan offerings, making it more accessible and comprehensible.
- Respond to queries effectively, incorporating feedback to enhance your accuracy.
- Handle data securely and update your knowledge base with the latest research.
- Maintain a feedback loop for continuous improvement and user support.
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

def main():
    st.title("AI Assistant - Memo Writer")

    # Password protection
    if 'password_correct' not in st.session_state:
        password = st.text_input("Enter password:", type="password")
        if password == st.secrets["password"]["APP_PASSWORD"]:
            st.session_state['password_correct'] = True
            st.experimental_rerun()
        elif password:
            st.error("Password incorrect")
        return

    # AWS S3 bucket name
    bucket_name = st.secrets["aws"]["s3_bucket_name"]

    # Initialize session state for job IDs and extracted texts
    if 'job_ids' not in st.session_state:
        st.session_state['job_ids'] = {}
    if 'document_texts' not in st.session_state:
        st.session_state['document_texts'] = {}

    # Slot 1 - Document Upload and Text Extraction
    st.subheader("Slot 1 [Suggested Upload = Marketing Materials]")
    uploaded_file1 = st.file_uploader("Upload a document for Slot 1", type=['pdf', 'docx', 'png', 'jpg'], key="slot1")

    # Placeholder for Slot 1 status and preview
    slot1_status_placeholder = st.empty()
    slot1_preview_placeholder = st.empty()

    if uploaded_file1 is not None and 'slot1' not in st.session_state.document_texts:
        # Upload the file to S3
        object_name1 = uploaded_file1.name
        upload_to_s3(uploaded_file1, bucket_name, object_name1)

        # Start Textract job and save Job ID in session state
        job_id1 = start_text_detection(bucket_name, object_name1)
        st.session_state.job_ids['slot1'] = job_id1
        st.session_state['slot1_object_name'] = object_name1
        slot1_status_placeholder.info("Slot 1: Text extraction started... Please wait.")

    # Check if Slot 1 job is in progress
    if 'slot1' in st.session_state.job_ids:
        job_id1 = st.session_state.job_ids['slot1']
        status = is_job_complete(job_id1)
        if status == 'SUCCEEDED':
            document_text1 = get_text_from_response(job_id1)
            st.session_state.document_texts['slot1'] = document_text1
            del st.session_state.job_ids['slot1']  # Remove job ID as it's completed
            slot1_status_placeholder.success("Slot 1: Document text extracted successfully.")

            # Display a preview of the extracted text
            slot1_preview_placeholder.subheader("Slot 1 - Preview of Extracted Text:")
            preview_text1 = document_text1[:500] + '...' if len(document_text1) > 500 else document_text1
            slot1_preview_placeholder.text_area("Slot 1 Extracted Text", preview_text1, height=200, key="slot1_preview")
        elif status == 'FAILED':
            slot1_status_placeholder.error("Slot 1: Failed to extract text from the document.")
            del st.session_state.job_ids['slot1']  # Remove job ID as it's completed
        else:
            # Job is still in progress, show waiting message
            slot1_status_placeholder.info("Slot 1: Text extraction in progress... Please wait.")
    elif 'slot1' in st.session_state.document_texts:
        # Confirmation message if extraction is already done
        slot1_status_placeholder.success("Slot 1: Document text extracted successfully.")

    # Slot 2 - Document Upload and Text Extraction
    st.subheader("Slot 2 [Suggested Upload = Term Sheet]")
    uploaded_file2 = st.file_uploader("Upload a document for Slot 2", type=['pdf', 'docx', 'png', 'jpg'], key="slot2")

    # Placeholder for Slot 2 status and preview
    slot2_status_placeholder = st.empty()
    slot2_preview_placeholder = st.empty()

    if uploaded_file2 is not None and 'slot2' not in st.session_state.document_texts:
        # Upload the file to S3
        object_name2 = uploaded_file2.name
        upload_to_s3(uploaded_file2, bucket_name, object_name2)

        # Start Textract job and save Job ID in session state
        job_id2 = start_text_detection(bucket_name, object_name2)
        st.session_state.job_ids['slot2'] = job_id2
        st.session_state['slot2_object_name'] = object_name2
        slot2_status_placeholder.info("Slot 2: Text extraction started... Please wait.")

    # Check if Slot 2 job is in progress
    if 'slot2' in st.session_state.job_ids:
        job_id2 = st.session_state.job_ids['slot2']
        status = is_job_complete(job_id2)
        if status == 'SUCCEEDED':
            document_text2 = get_text_from_response(job_id2)
            st.session_state.document_texts['slot2'] = document_text2
            del st.session_state.job_ids['slot2']  # Remove job ID as it's completed
            slot2_status_placeholder.success("Slot 2: Document text extracted successfully.")

            # Display a preview of the extracted text
            slot2_preview_placeholder.subheader("Slot 2 - Preview of Extracted Text:")
            preview_text2 = document_text2[:500] + '...' if len(document_text2) > 500 else document_text2
            slot2_preview_placeholder.text_area("Slot 2 Extracted Text", preview_text2, height=200, key="slot2_preview")
        elif status == 'FAILED':
            slot2_status_placeholder.error("Slot 2: Failed to extract text from the document.")
            del st.session_state.job_ids['slot2']  # Remove job ID as it's completed
        else:
            # Job is still in progress, show waiting message
            slot2_status_placeholder.info("Slot 2: Text extraction in progress... Please wait.")
    elif 'slot2' in st.session_state.document_texts:
        # Confirmation message if extraction is already done
        slot2_status_placeholder.success("Slot 2: Document text extracted successfully.")

    # Slot 3 - Pricing Data Input
    st.subheader("Slot 3 [Suggested Upload = Pricing Data]")
    pricing_data = st.text_area("Paste in pricing data for the loan", "", height=200, key="slot3")

    # Placeholder for Slot 3 preview
    slot3_preview_placeholder = st.empty()

    if pricing_data:
        # Store the pricing data in session state
        st.session_state.document_texts['slot3'] = pricing_data

        # Display a preview of the pricing data
        slot3_preview_placeholder.subheader("Slot 3 - Preview of Pricing Data:")
        preview_text3 = pricing_data[:500] + '...' if len(pricing_data) > 500 else pricing_data
        slot3_preview_placeholder.text_area("Slot 3 Pricing Data", preview_text3, height=200, key="slot3_preview")

    # User input
    user_message = st.text_input("Enter any additional instructions or information:", "")

    if st.button("Generate Memo"):
        with st.spinner("Generating your memo..."):
            # Include extracted texts as additional context if available
            additional_context = ""
            if 'slot1' in st.session_state.document_texts:
                additional_context += f"\n\n[Marketing Materials]:\n{st.session_state.document_texts['slot1']}"
            if 'slot2' in st.session_state.document_texts:
                additional_context += f"\n\n[Term Sheet]:\n{st.session_state.document_texts['slot2']}"
            if 'slot3' in st.session_state.document_texts:
                additional_context += f"\n\n[Pricing Data]:\n{st.session_state.document_texts['slot3']}"

            # Prepare the prompt for the assistant
            prompt = f"""
{ASSISTANT_ROLE_DESCRIPTION}

Please write an indication of interest memo based on the provided documents and data.

{additional_context}

{user_message}
"""

            # Create a message in the thread
            message = client.beta.threads.messages.create(
                thread_id=THREAD_ID,
                role="user",
                content=prompt
            )

            # Run the assistant with the instructions
            run = client.beta.threads.runs.create(
                thread_id=THREAD_ID,
                assistant_id=ASSIS_ID,
                instructions="Please generate the memo as per the guidelines."
            )

            # Wait for the run to complete and get the response
            response = wait_for_run_completion(THREAD_ID, run.id)

            if response:
                st.write("**Generated Memo:**")
                st.write(response)
            else:
                st.error("Failed to get a response. Please try again.")

            # Optionally, display run steps (for debugging)
            # run_steps = client.beta.threads.runs.steps.list(thread_id=THREAD_ID, run_id=run.id)
            # st.write("Run Steps:", run_steps.data[0])

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
                # Assuming the assistant's reply is the last message
                last_message = messages.data[0]
                response = last_message.content[0].text.value
                return response
        except Exception as e:
            logging.error(f"An error occurred while retrieving the run: {e}")
            return None
        
        logging.info("Waiting for run to complete...")
        time.sleep(sleep_interval)

if __name__ == "__main__":
    main()

