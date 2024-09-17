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
from pdf2image import convert_from_bytes
from PIL import Image

# Use Streamlit's secrets management
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Constants
MODEL = "GPT-4o-mini"  # Keeping the original model as per your request

# Initialize boto3 session with credentials from secrets.toml
session = boto3.Session(
    aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
    aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
    region_name=st.secrets["aws"]["region_name"]
)

# Create AWS clients
textract = session.client('textract')

# Set up logging
logging.basicConfig(level=logging.INFO)

def extract_text_synchronously(file_bytes, file_type):
    text = ''

    if file_type == 'application/pdf':
        # Convert PDF to images
        images = convert_from_bytes(file_bytes)
        for image in images:
            # Convert image to bytes
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            # Call Textract on each image
            response = textract.detect_document_text(Document={'Bytes': img_bytes})
            text += get_text_from_response(response)
    else:
        # Process image files directly
        response = textract.detect_document_text(Document={'Bytes': file_bytes})
        text = get_text_from_response(response)
    return text

def get_text_from_response(response):
    extracted_text = ''
    for block in response['Blocks']:
        if block['BlockType'] == 'LINE':
            extracted_text += block['Text'] + '\n'
    return extracted_text

def truncate_text(text, max_chars=6000):
    """Truncate text to a maximum number of characters."""
    if len(text) > max_chars:
        return text[:max_chars] + '...'
    else:
        return text

def get_assistant_response(user_message, additional_context=None):
    # Construct the messages array
    messages = [
        {"role": "system", "content": "Please address the user as Preston."},
        {"role": "user", "content": user_message}
    ]

    # Include additional context if available
    if additional_context:
        # Truncate the additional context if necessary
        additional_context = truncate_text(additional_context, max_chars=6000)
        messages.append({"role": "system", "content": additional_context})

    # Make the API call
    response = openai.ChatCompletion.create(
        model=MODEL,
        messages=messages,
        temperature=0.7  # Adjust as needed
    )

    # Extract the assistant's reply
    assistant_reply = response['choices'][0]['message']['content']
    return assistant_reply

def main():
    st.title("AI Assistant - Memo Writer")

    # Slot 1 - Document Upload and Text Extraction
    st.subheader("Slot 1 [Suggested Upload = Marketing Materials]")
    uploaded_file1 = st.file_uploader("Upload a document for Slot 1", type=['pdf', 'png', 'jpg'], key="slot1")

    document_text1 = None

    if uploaded_file1 is not None:
        # Read file content into memory
        document_bytes1 = uploaded_file1.read()
        file_type1 = uploaded_file1.type
        try:
            with st.spinner("Slot 1: Extracting text from the document..."):
                document_text1 = extract_text_synchronously(document_bytes1, file_type1)
            st.success("Slot 1: Document text extracted successfully.")

            # Display a preview of the extracted text
            st.subheader("Slot 1 - Preview of Extracted Text:")
            preview_text1 = document_text1[:500] + '...' if len(document_text1) > 500 else document_text1
            st.text_area("Slot 1 Extracted Text", preview_text1, height=200, key="slot1_preview")
        except Exception as e:
            st.error(f"Slot 1: Failed to extract text from the document. Error: {e}")

    # Slot 2 - Document Upload and Text Extraction
    st.subheader("Slot 2 [Suggested Upload = Term Sheet]")
    uploaded_file2 = st.file_uploader("Upload a document for Slot 2", type=['pdf', 'png', 'jpg'], key="slot2")

    document_text2 = None

    if uploaded_file2 is not None:
        # Read file content into memory
        document_bytes2 = uploaded_file2.read()
        file_type2 = uploaded_file2.type
        try:
            with st.spinner("Slot 2: Extracting text from the document..."):
                document_text2 = extract_text_synchronously(document_bytes2, file_type2)
            st.success("Slot 2: Document text extracted successfully.")

            # Display a preview of the extracted text
            st.subheader("Slot 2 - Preview of Extracted Text:")
            preview_text2 = document_text2[:500] + '...' if len(document_text2) > 500 else document_text2
            st.text_area("Slot 2 Extracted Text", preview_text2, height=200, key="slot2_preview")
        except Exception as e:
            st.error(f"Slot 2: Failed to extract text from the document. Error: {e}")

    # User input
    user_message = st.text_input("Ask a question about cryptocurrency:", "What is mining?")

    if st.button("Get Answer"):
        with st.spinner("Processing your question..."):
            # Combine extracted texts from both slots
            additional_context = ""
            if document_text1:
                additional_context += f"Additional context from Slot 1 document:\n{document_text1}\n\n"
            if document_text2:
                additional_context += f"Additional context from Slot 2 document:\n{document_text2}\n\n"

            # Get the assistant's response
            response = get_assistant_response(user_message, additional_context)

            if response:
                st.write("Assistant's Response:", response)
            else:
                st.error("Failed to get a response. Please try again.")

if __name__ == "__main__":
    main()

