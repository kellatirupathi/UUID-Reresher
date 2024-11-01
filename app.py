import re
import json
import requests
import streamlit as st
import pandas as pd
from tempfile import NamedTemporaryFile

# Regular expression pattern for matching UUIDs
uuid_pattern = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')

# Initialize the UUID mapping table in session state if it doesn't exist
if "uuid_mapping" not in st.session_state:
    st.session_state.uuid_mapping = []

# Function to get a batch of new UUIDs from the external UUID generator API in chunks
def get_batch_of_uuids(total_uuids_needed, chunk_size=400):
    uuid_list = []
    try:
        while len(uuid_list) < total_uuids_needed:
            batch_size = min(chunk_size, total_uuids_needed - len(uuid_list))
            response = requests.get(f"https://www.uuidgenerator.net/api/version4/{batch_size}")
            if response.status_code == 200:
                # The API returns UUIDs as plain text separated by newlines
                new_uuids = response.text.strip().splitlines()
                uuid_list.extend(new_uuids)
            else:
                st.error("Failed to fetch new UUIDs from the API.")
                return []
    except Exception as e:
        st.error(f"Error fetching UUIDs from API: {e}")
        return []

    return uuid_list

# Recursive function to replace UUIDs in JSON data using external API
def replace_uuids_recursively(data, uuid_batch, uuid_mapping):
    if isinstance(data, str):
        # Replace UUIDs found in strings with a new one from the batch
        def replacement_func(match):
            old_uuid = match.group(0)
            new_uuid = uuid_batch.pop(0) if uuid_batch else old_uuid
            uuid_mapping.append({"Original UUID": old_uuid, "New UUID": new_uuid})
            return new_uuid
        
        return uuid_pattern.sub(replacement_func, data)
    elif isinstance(data, dict):
        return {k: replace_uuids_recursively(v, uuid_batch, uuid_mapping) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_uuids_recursively(element, uuid_batch, uuid_mapping) for element in data]
    else:
        return data

# Function to count items in JSON data, subtopic-wise if applicable
def count_questions(data):
    if isinstance(data, dict):
        subtopic_counts = {}
        for key, value in data.items():
            if isinstance(value, list):
                subtopic_counts[key] = len(value)
        
        if subtopic_counts:
            return subtopic_counts
        
        for value in data.values():
            if isinstance(value, list):
                return {"Total Questions": len(value)}
    elif isinstance(data, list):
        return {"Total Questions": len(data)}
    return {"Total Questions": 0}

# Streamlit interface
st.title("UUID Refresher")

# File uploader
uploaded_file = st.file_uploader("Choose a JSON file", type="json")

if uploaded_file is not None:
    try:
        json_data = json.load(uploaded_file)
    except json.JSONDecodeError:
        st.error("Uploaded file is not a valid JSON file.")
        st.stop()

    # Count UUIDs in JSON data for replacement
    all_uuids = uuid_pattern.findall(json.dumps(json_data))
    num_uuids = len(all_uuids)
    st.write(f"Number of UUIDs detected for replacement: {num_uuids}")

    # Count questions or main items
    question_counts = count_questions(json_data)
    if "Total Questions" in question_counts:
        st.write(f"Number of questions detected: {question_counts['Total Questions']}")
    else:
        st.write("Counts per subtopic:")
        for subtopic, count in question_counts.items():
            st.write(f"- {subtopic}: {count}")

    # Process button
    if st.button("Process UUIDs"):
        # Fetch the required number of UUIDs in chunks
        uuid_batch = get_batch_of_uuids(num_uuids, chunk_size=100)
        
        if len(uuid_batch) != num_uuids:
            st.error("Failed to fetch enough UUIDs from the API.")
        else:
            # Clear previous UUID mappings
            st.session_state.uuid_mapping = []
            
            # Replace UUIDs in JSON data and update the session state
            modified_json_data = replace_uuids_recursively(json_data, uuid_batch, st.session_state.uuid_mapping)

            # Store the modified JSON data temporarily for download
            with NamedTemporaryFile("w+", encoding="utf-8", delete=False, suffix=".json") as temp_file:
                json.dump(modified_json_data, temp_file, indent=4, ensure_ascii=False)
                temp_file.seek(0)
                st.download_button(
                    label="Download Processed JSON",
                    data=temp_file.read(),
                    file_name="processed_json.json",
                    mime="application/json"
                )

    # Display the UUID mapping table if there is data
    if st.session_state.uuid_mapping:
        uuid_df = pd.DataFrame(st.session_state.uuid_mapping)
        st.write("UUID Mapping Table:")
        st.dataframe(uuid_df)
