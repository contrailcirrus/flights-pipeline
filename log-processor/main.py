import os
import io
import pandas as pd
import orjson # Faster than json, good for large logs
from google.cloud import storage
from typing import Optional

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "nick-sandbox-public")

# Define severity levels (assuming standard GCP logging levels)
SEVERITY_LEVELS = ["DEFAULT", "DEBUG", "INFO", "NOTICE", "WARNING", "ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
SEVERITY_RANK = {level: rank for rank, level in enumerate(SEVERITY_LEVELS)}

class LogParser:
    def __init__(self, bucket_name: str):
        """
        Initialize the parser with a specific GCS bucket.
        Environment variable GOOGLE_APPLICATION_CREDENTIALS must be set.
        """
        self.bucket_name = bucket_name
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(self.bucket_name)
        self.df: Optional[pd.DataFrame] = None  

    def parse(self, file_path: str) -> pd.DataFrame:
        """
        Reads a JSON file from GCS, parses jsonPayload and severity,
        and returns a Pandas DataFrame.
        """
        print(f"Attempting to download: gs://{self.bucket_name}/{file_path}")
        blob = self.bucket.blob(file_path)

        # Download as bytes. For extremely large files, we might want to 
        # stream line by line using blob.open("r"), but download_as_bytes 
        # is efficient for files fitting in memory.
        try:
            content_bytes = blob.download_as_bytes()
        except Exception as e:
            print(f"Error downloading file: {e}")
            return pd.DataFrame()

        processed_rows = []

        # Split by newline for NDJSON format
        for line in content_bytes.splitlines():
            if not line.strip():
                continue
                
            try:
                # Parse the raw JSON line
                record = orjson.loads(line)
                
                # We are interested in flattening jsonPayload and adding severity
                # 1. Start with the payload contents
                flat_record = record.get("jsonPayload", {})
                
                # If jsonPayload is null or not a dict, handle gracefully
                if flat_record is None:
                    flat_record = {}
                elif not isinstance(flat_record, dict):
                    # Handle case where payload might be a simple string
                    flat_record = {"message": str(flat_record)}
                
                # 2. Add severity (if it exists in the root object)
                if "severity" in record:
                    flat_record["severity"] = record["severity"]
                
                processed_rows.append(flat_record)

            except orjson.JSONDecodeError:
                print(f"Skipping malformed JSON line")
                continue

        # Create DataFrame
        # Pandas handles the "ragged" aspect automatically by filling missing keys with NaN
        df = pd.DataFrame(processed_rows)
        self.df = df 
        return df
    
    def update_data(self, new_df: pd.DataFrame):
        """
        Update the internal DataFrame with new data. This can be used for
        incremental updates or merging with existing data.
        """            
        if new_df is None:
            print("Warning: overriding existing DataFrame with None.")
        self.df = new_df

    def get_flight_ids(self) -> pd.Series[str]:
        """
        Example method to extract unique flight identifiers from the DataFrame.
        Assumes there is a 'flight_id' column in the DataFrame.
        """
        if self.df is None:
            print("DataFrame is empty. No data to extract.")
            return pd.Series(dtype=str)
        
        if 'flight_id' not in self.df.columns:
            print("Warning: 'flight_id' column not found in DataFrame.")
            return pd.Series(dtype=str)
        
        return self.df['flight_id'].dropna().unique()
    
    def get_flight_ids_clean(self) -> pd.Series[str]:
        """
        Return unique flight_id values that are processed cleanly to produce
        Jobs to be put in the PubSub queue.
        Clean jobs are flight_ids not associated with any rows severity
        greater than INFO and with no messages containing the string "skipping".
        """
        if self.df is None:
            print("DataFrame is empty. No data to extract.")
            return pd.Series(dtype=str)
        
        if 'flight_id' not in self.df.columns:
            print("Warning: 'flight_id' column not found in DataFrame.")
            return pd.Series(dtype=str)
        
        all_flight_ids = self.get_flight_ids()

        get_error_flight_ids = self.get_flight_ids_failed()
        get_skipped_flight_ids = self.get_flight_ids_skipped()
        # Clean flight_ids are those that are not in either the error or skipped sets
        clean_flight_ids = set(all_flight_ids) - set(get_error_flight_ids) - set(get_skipped_flight_ids)
        return pd.Series(list(clean_flight_ids))

    def get_flight_ids_skipped(self) -> pd.Series[str]:
        """
        Return unique flight_id values that have any rows with message fields
        containing the word 'skipped'.
        """
        if self.df is None:
            print("DataFrame is empty. No data to extract.")
            return pd.Series(dtype=str)
        
        if 'flight_id' not in self.df.columns:
            print("Warning: 'flight_id' column not found in DataFrame.")
            return pd.Series(dtype=str)
        
        if 'message' not in self.df.columns:
            print("Warning: 'message' column not found in DataFrame.")
            return pd.Series(dtype=str)
        
        # Filter rows where 'message' contains 'skipped'
        skipped_flights = self.df[self.df['message'].str.contains('skipping', case=False, na=False)]
        
        # Return unique flight_ids from the skipped subset
        return skipped_flights['flight_id'].dropna().unique()
    

    def get_flight_ids_failed(self) -> pd.Series[str]:
        """
        Return unique flight_id values that have any rows with severity ERROR or higher.
        """
        if self.df is None:
            print("DataFrame is empty. No data to extract.")
            return pd.Series(dtype=str)
        
        if 'flight_id' not in self.df.columns:
            print("Warning: 'flight_id' column not found in DataFrame.")
            return pd.Series(dtype=str)
        
        # Filter rows with severity WARNING or higher
        failed_flights = self.df[self.df['severity'].apply(lambda x: SEVERITY_RANK.get(x, -1) >= SEVERITY_RANK["WARNING"])]
        
        # Return unique flight_ids from the failed subset
        return failed_flights['flight_id'].dropna().unique()

    def get_flight_ids_dirty(self) -> pd.Series[str]:
        """
        Return unique flight_id values that are considered "dirty" '
        (i.e., have any rows with severity > INFO or messages containing 'skipped').
        """
        if self.df is None:
            print("DataFrame is empty. No data to extract.")
            return pd.Series(dtype=str)
        
        if 'flight_id' not in self.df.columns:
            print("Warning: 'flight_id' column not found in DataFrame.")
            return pd.Series(dtype=str)
        
        # Get sets of flight_ids that are either failed or skipped
        failed_flight_ids = self.get_flight_ids_failed()
        skipped_flight_ids = self.get_flight_ids_skipped()
        
        # Combine the two sets to get all dirty flight_ids
        dirty_flight_ids = pd.concat([pd.DataFrame({'flight_id': failed_flight_ids}), pd.DataFrame({'flight_id': skipped_flight_ids})])
        
        return dirty_flight_ids['flight_id'].dropna().unique()

# Example Usage logic for testing
if __name__ == "__main__":
    # Configuration via Env Vars
    FILE_PATH = os.getenv("GCS_FILE_PATH", "twjf-logs/12/10:00:00_10:59:59_S0.json")

    parser = LogParser(GCS_BUCKET_NAME)
    df = parser.parse(FILE_PATH)

    flights = parser.get_flight_ids()
    print(f"\nUnique flight_ids: {flights}")

    clean_flights = parser.get_flight_ids_clean()
    print(f"\nClean flight_ids: {clean_flights}")

    dirty_flights = parser.get_flight_ids_dirty()
    print(f"\nDirty flight_ids: {dirty_flights}")

    error_flights = parser.get_flight_ids_failed()
    print(f"\nFailed flight_ids: {error_flights}")

    skipped_flights = parser.get_flight_ids_skipped()
    print(f"\nSkipped flight_ids: {skipped_flights}")