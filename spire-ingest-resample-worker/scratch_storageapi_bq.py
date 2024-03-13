"""
This code sample demonstrates how to write records in pending mode
using the low-level generated client for Python.

ref: https://github.com/googleapis/python-bigquery-storage/blob/26005329a83512fcc854d7a991f95a1a13474510/samples/snippets/append_rows_pending.py
"""

from datetime import datetime

from google.cloud import bigquery_storage_v1
from google.cloud.bigquery_storage_v1 import types
from google.cloud.bigquery_storage_v1 import writer
from google.protobuf import descriptor_pb2

import bq_spire_flights_resampled_pb2 as record_pb


def create_row_data():
    ts = "2024-03-13T09:24:41Z"
    row = record_pb.SpireFlightResampledRecord()
    row.timestamp = int(datetime.fromisoformat(ts).timestamp())
    row.latlon = '{"type": "Point", "coordinates": [-119.3, 33.4]}'
    row.altitude_baro = 36344
    row.flight_level = 360
    row.imputed = True
    row.icao_address = "foo4bar"
    row.flight_id = "3333-abss-2112..."
    return row.SerializeToString()


def create_append_row_request() -> types.AppendRowsRequest:
    proto_rows = types.ProtoRows()
    proto_rows.serialized_rows.append(create_row_data())

    # Set an offset to allow resuming this stream if the connection breaks.
    # Keep track of which requests the server has acknowledged and resume the
    # stream at the first non-acknowledged message. If the server has already
    # processed a message with that offset, it will return an ALREADY_EXISTS
    # error, which can be safely ignored.
    #
    # The first request must always have an offset of 0.
    request = types.AppendRowsRequest()
    request.offset = 0
    proto_data = types.AppendRowsRequest.ProtoData()
    proto_data.rows = proto_rows
    request.proto_rows = proto_data
    return request


def write_with_stream_writer(
    client: bigquery_storage_v1.BigQueryWriteClient, request: types.AppendRowsRequest
):
    """
    Create a write stream, write some sample data, and commit the stream.
    Close all resources when done.
    """
    parent = client.table_path(
        "contrails-301217", "flights_pipeline_dev", "spire_flights_resampled_dev"
    )
    write_stream = types.WriteStream()

    # When creating the stream, choose the type. Use the PENDING type to wait
    # until the stream is committed before it is visible. See:
    # https://cloud.google.com/bigquery/docs/reference/storage/rpc/google.cloud.bigquery.storage.v1#google.cloud.bigquery.storage.v1.WriteStream.Type
    write_stream.type_ = types.WriteStream.Type.PENDING
    write_stream = client.create_write_stream(parent=parent, write_stream=write_stream)
    stream_name = write_stream.name

    # Create a template with fields needed for the first request.
    request_template = types.AppendRowsRequest()

    # The initial request must contain the stream name.
    request_template.write_stream = stream_name

    # So that BigQuery knows how to parse the serialized_rows, generate a
    # protocol buffer representation of your message descriptor.
    proto_schema = types.ProtoSchema()
    proto_descriptor = descriptor_pb2.DescriptorProto()
    record_pb.SpireFlightResampledRecord.DESCRIPTOR.CopyToProto(proto_descriptor)
    proto_schema.proto_descriptor = proto_descriptor
    proto_data = types.AppendRowsRequest.ProtoData()
    proto_data.writer_schema = proto_schema
    request_template.proto_rows = proto_data

    # Some stream types support an unbounded number of requests. Construct an
    # AppendRowsStream to send an arbitrary number of requests to a stream.
    append_rows_stream = writer.AppendRowsStream(client, request_template)
    response_future_1 = append_rows_stream.send(request)

    # NOTE: exception specifics can't be extracted here
    # response_future_1.exception() references a field which isn't present on any
    # of the objects here...
    # "400 Errors found while processing rows. Please refer to the row_errors field for details."
    print(response_future_1.result())

    # Shutdown background threads and close the streaming connection.
    append_rows_stream.close()

    # A PENDING type stream must be "finalized" before being committed. No new
    # records can be written to the stream after this method has been called.
    client.finalize_write_stream(name=write_stream.name)

    # Commit the stream you created earlier.
    batch_commit_write_streams_request = types.BatchCommitWriteStreamsRequest()
    batch_commit_write_streams_request.parent = parent
    batch_commit_write_streams_request.write_streams = [write_stream.name]
    client.batch_commit_write_streams(batch_commit_write_streams_request)

    print(f"Writes to stream: '{write_stream.name}' have been committed.")


bq_write_client = bigquery_storage_v1.BigQueryWriteClient()

write_with_stream_writer(bq_write_client, create_append_row_request())
