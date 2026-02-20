import os
import pandas as pd
import orjson # Faster than json, good for large logs
from smart_open import open
from datetime import datetime, timezone
from google.cloud import storage
from typing import Optional

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "contrails-301217-fp-prod-trajectory-worker-job-factory")

# Define severity levels (assuming standard GCP logging levels)
SEVERITY_LEVELS = ["DEFAULT", "DEBUG", "INFO", "NOTICE", "WARNING", "ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
SEVERITY_RANK = {level: rank for rank, level in enumerate(SEVERITY_LEVELS)}

TWJF_START_WORK_MSG = 'start work'
TWJF_SKIP_MSG_KEYWORD = 'skipping'
TWJF_LAST_MOD_MSG = 'resample step done'


GKE_LOG_FILENAME_DATETIME_FORMAT = "%H:%M:%S"

class LogParser:
    def __init__(self, bucket_name: str, start_time: Optional[str] = None, end_time: Optional[str] = None):
        """
        Initialize the parser with a specific GCS bucket.
        Optionally specify start_time and end_time as ISO-formatted strings.
        Environment variable GOOGLE_APPLICATION_CREDENTIALS must be set.
        """
        self.bucket_name = bucket_name
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(self.bucket_name)
        self.df: Optional[pd.DataFrame] = None
        self.start_time = datetime.fromisoformat(start_time) if start_time else None
        self.end_time = datetime.fromisoformat(end_time) if end_time else None

    @staticmethod
    def convert_datetime_to_utc(dt: datetime) -> datetime:
        """
        Convert a datetime object to UTC timezone if it is timezone-aware.
        If the datetime is naive (no timezone), it is returned as-is.
        """
        # Only convert if timezone-aware
        if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
            return dt.astimezone(timezone.utc)
        else:
            return dt.replace(tzinfo=timezone.utc)
        
    @staticmethod
    def gke_log_name_to_end_time(file_name: str) -> Optional[datetime]:
        """
        Extract a datetime object from a GKE log file name.
        GKE log file names typically look like this:
        `11:00:00_11:59:59_S0.json`
        """

        hr_min_sec = file_name.split("_")[1]  # Extract the end time part
        try:
            return datetime.strptime(hr_min_sec, GKE_LOG_FILENAME_DATETIME_FORMAT)
        except ValueError:
            return None


    def construct_blob_paths_from_date_range(self, start_time: datetime, end_time: datetime) -> list[str]:
        """
        Construct GCS blob paths based on a given date range.
        Assumes the default Google Cloud GKE log sink path structure.
        Returns a list of blob paths for the specified date range.
        All hourly blobs are included.

        Note: Typical GKE log sink paths are in the format:
        gs://<bucket_name>/stderr/<year>/<month>/<day>/
        This function generates paths for all logs files within the specified date.
        """
        # TODO: could limit to specific hours to reduce the number of logs read in
        # This could help ensure better performance when we're only interested in a
        # specific subset during a dense set of logs.

        # Ensure datetimes are UTC
        start_time = LogParser.convert_datetime_to_utc(start_time)
        end_time = LogParser.convert_datetime_to_utc(end_time)
        
        day_index = start_time.replace(minute=0, second=0, microsecond=0)  # Start at the beginning of the hour
        blob_paths = []
        while day_index <= end_time:
            prefix = f"stderr/{day_index.year:04d}/{day_index.month:02d}/{day_index.day:02d}/"
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            print(f"Found {len(blobs)} blobs for prefix: {prefix}")
            if day_index.year == start_time.year and day_index.month == start_time.month and day_index.day == start_time.day:
                # If we're on the first day, filter blobs to only include those starting from the start_time
                try:
                    print(f"Filtering blobs for start_time: {start_time.time()}")
                    blobs = [blob for blob in blobs if LogParser.gke_log_name_to_end_time(blob.name).time() >= start_time.time()]
                except Exception:
                    # If any error occurs during filtering, keep all blobs for this day before start_time
                    pass
            if day_index.year == end_time.year and day_index.month == end_time.month and day_index.day == end_time.day:
                # If we're on the last day, filter blobs to only include those up to the end_time
                try:
                    print(f"Filtering blobs for end_time: {end_time.time()}")
                    blobs = [blob for blob in blobs if LogParser.gke_log_name_to_end_time(blob.name).time() <= end_time.time()]
                except Exception:
                    # If any error occurs during filtering, keep all blobs for this day after end_time
                    pass

            blob_paths.extend([blob.name for blob in blobs])
            day_index += pd.Timedelta(days=1)

        return blob_paths

    @staticmethod
    def read_json_log_file(uri: str) -> list[dict[str: str]]:
        """ Read json log file streaming line by line.
        
        Assumes logs are newline delimited JSON formatted. Uses smart_open to 
        stream file line by line.
        
        Parameters
        ----------
        uri: str
            Valid uri to blob in bucket, or local file path.
        
        Returns:
            List of key-value pairs of elements parsed from the JSON logs.        
        """

        processed_rows = []
        for line in open(uri):
            # Process the data (line is a bytes object for binary mode)
            if not line.strip():
                continue
            try:
                record = orjson.loads(line)
                flat_record = record.get("jsonPayload", {})
                
                # If jsonPayload is null or not a dict, handle gracefully
                if flat_record is None:
                    flat_record = {}
                elif not isinstance(flat_record, dict):
                    # Handle case where payload might be a simple string
                    flat_record = {"message": str(flat_record)}
                if "severity" in record:
                    flat_record["severity"] = record["severity"]
                
                processed_rows.append(flat_record)

            except orjson.JSONDecodeError:
                print(f"Skipping malformed JSON line")
                continue
        return processed_rows
    

    def parse(self, start_time: Optional[str] = None, end_time: Optional[str] = None) -> pd.DataFrame:
        """
        Reads JSON files from GCS based on time range, parses jsonPayload and severity,
        and returns a Pandas DataFrame.
        Optionally specify start_time and end_time as ISO-formatted strings for this parse.

        Parameters
        ----------
        start_time : Optional[str]
            ISO-formatted string representing the start time for log parsing (e.g., "2024-06-01T10:00:00Z"). 
            If not provided, uses the instance's start_time.
        end_time : Optional[str]
            ISO-formatted string representing the end time for log parsing (e.g., "2024-06-01T12:00:00Z"). 
            If not provided, uses the instance's end_time.
        Returns
        -------
        pd.DataFrame
            A DataFrame containing the parsed log data, filtered by the specified date range 
            if start_time and end_time are provided. 
        """
        # Allow override of instance start/end time
        st = LogParser.convert_datetime_to_utc(datetime.fromisoformat(start_time) if start_time else self.start_time)
        et = LogParser.convert_datetime_to_utc(datetime.fromisoformat(end_time) if end_time else self.end_time)

        blobs = self.construct_blob_paths_from_date_range(st, et)
        print(f"Found {len(blobs)} log files in the specified date range.")

        for blob in blobs:
            uri = f"gs://{self.bucket_name}/{blob}"
            try:
                print(f"Opening file: {uri}")
                processed_rows = LogParser.read_json_log_file(uri)

                df = pd.DataFrame(processed_rows)

                self.df = pd.concat([self.df, df], ignore_index=True) if self.df is not None else df

            except Exception as e:
                print(f"Error streaming file: {e}")
                return pd.DataFrame()

        # convert timestamps
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'], format='ISO8601')
        self.df['start_time'] = pd.to_datetime(self.df['start_time'])
        self.df['end_time'] = pd.to_datetime(self.df['end_time'])

        # Filter the DataFrame by the specified date range if start_time and end_time are provided
        self.df = self.df[self.df['timestamp'].apply(lambda x: st <= x <= et)] if st and et else self.df

        return self.df
    
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
    
    def save_data(self, output_filename: str):
        """
        Save dataframe of parsed logs to file.
        
        Parameters
        ----------
            output_filename: 
        Filename to save the dataframe to.
        """

        if not self.df or len(self.df) == 0:
            print("No data to save.")

        self.df.to_csv(output_filename, compression="gzip")

    def process_per_flight_timing_stats(self) -> pd.DataFrame:
        """
        Get a dataframe with one row per `flight_id`, containing:
        included (bool), 
        initial_flight_time (float, minutes), 
        submitted flight_time (float, minutes), 
        start_time (timestamp), 
        end_time (timestamp)

        The start_time and end_time are the initial values at ingestion into the pipeline, not the
        values that are submitted as jobs.
        """
        columns = ["flight_id", "included", "flight_time", "submitted_flight_time", "start_time", "end_time"]
        output = pd.DataFrame(columns=columns)

        groups = self.df.groupby("flight_id")

        for flight_id, group in groups:
            included = ~ (group['message'].str.contains(TWJF_SKIP_MSG_KEYWORD).any() or 
                          group['severity'].apply(lambda x: SEVERITY_RANK.get(x, -1) >= SEVERITY_RANK["WARNING"]).any())
            flight_time = None
            start_line = group[group['message'] == TWJF_START_WORK_MSG]
            if len(start_line) == 1:
                flight_time = (start_line['end_time'] - start_line['start_time']).iloc[0].total_seconds()/60.0
            submitted_flight_time = None
            last_mod_line = group[group['message'] == TWJF_LAST_MOD_MSG]
            if len(last_mod_line) == 1:
                submitted_flight_time = (last_mod_line['end_time'] - last_mod_line['start_time']).iloc[0].total_seconds()/60.0

            row = [flight_id, included, flight_time, submitted_flight_time, start_line["start_time"], start_line['end_time']]

            output = pd.concat([output, pd.DataFrame(dict(zip(columns, row)))])

        return output

# Example Usage logic for testing
if __name__ == "__main__":
    # Configuration via Env Vars
    START_TIME = os.getenv("LOG_START_TIME")  # e.g. "2024-06-01T10:00:00+00:00"
    END_TIME = os.getenv("LOG_END_TIME")      # e.g. "2024-06-01T12:00:00+00:00"
    PREFIX = os.getenv("GCS_LOG_PREFIX", "twjf-logs/")

    parser = LogParser(GCS_BUCKET_NAME, start_time=START_TIME, end_time=END_TIME)
    df = parser.parse_range(prefix=PREFIX)

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