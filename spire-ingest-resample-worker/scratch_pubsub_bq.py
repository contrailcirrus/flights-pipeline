"""
Scratch scripting to test publishing of a JSON blob to pubsub, and integration/streaming to BQ table
"""

from concurrent import futures

from google.cloud import pubsub_v1
from tests.stubs.stub import pubsub_bq_out


client = pubsub_v1.PublisherClient()
topic = "projects/contrails-301217/topics/spire-ingest-resample-worker-bigquery-dev"
job_future = client.publish(topic, pubsub_bq_out)
job_future.add_done_callback(lambda future: print(future.result()))
futures.wait([job_future], return_when=futures.ALL_COMPLETED)
