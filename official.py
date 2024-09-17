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
openai.api_key = st.secrets["openai"]["api_key"]

# Initialize boto3 session with credentials from secrets.toml
session = boto3.Session(
    aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
    aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
    region_name=st.secrets["aws"]["region_name"]
)

# Create clients
s3 = session.client('s3')
textract = session.client('textract')

# Set up logging
logging.basicConfig(level=logging.INFO)

# Constants
MODEL = "GPT-4o-mini"
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
    while True:
        response = textract.get_document_text_detection(JobId=job_id)
        status = response['JobStatus']
        if status == 'SUCCEEDED':
            return True
        elif status == 'FAILED':
            raise Exception("Text detection job failed.")
        else:
            time.sleep(5)  # Wait before polling again

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

    # Optional document upload
    uploaded_file = st.file_uploader("Upload a document (PDF, DOCX, etc.)", type=['pdf', 'docx', 'png', 'jpg'])

    document_text = None

    if uploaded_file is not None:
        # Upload the file to S3
        bucket_name = st.secrets["aws"]["bucket_name"]
        object_name = uploaded_file.name
        upload_to_s3(uploaded_file, bucket_name, object_name)

        # Start Textract job
        job_id = start_text_detection(bucket_name, object_name)

        # Wait for the job to complete
        if is_job_complete(job_id):
            # Get the extracted text
            document_text = get_text_from_response(job_id)
            st.success("Document text extracted successfully.")
        else:
            st.error("Failed to extract text from the document.")

    # User input
    user_message = st.text_input("Ask a question about cryptocurrency:", "What is mining?")

    if st.button("Get Answer"):
        with st.spinner("Processing your question..."):
            # If document_text is available, include it as additional context
            if document_text:
                user_message += f"\n\nAdditional context from uploaded document:\n{document_text}"

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

