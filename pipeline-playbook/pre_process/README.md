# Pre-processing before flights-pipeline run

Before running the flights pipeline on Spire data to generate a trajectory inventory, follow these steps, then proceed to the instructions in the `playbook` directory for running the flights-pipeline.

The basic steps are outlined below.

## Set up Met zarr store

We keep a separate copy of the ECWMF zarr store ERA5 data to use for a given flights-pipeline run. 
That copy is in the `gs://contrails-301217-ecmwf-era5-zarr-v2-staging/` GCS bucket.
The data in this bucket is copied into a Hyperdisk accessible to the flights-pipeline trajectory-worker pods for quick, inexpensive Met data access.

### Delete existing data in staging zarr store

If the data in the staging zarr store GCS bucket is not the needed data, delete it.
Note that this can take a while - several hours for over a year of data.
I spin up a VM, and run `gsutil -m rm -R "gs://contrails-301217-ecmwf-era5-zarr-v2-staging/*"`

__Note__: This may be more efficient using [Lifecycle Rules](https://docs.cloud.google.com/storage/docs/deleting-objects#delete-objects-in-bulk) or one of the other bulk deletion methods described in the GCS documentation.

## Copy zarr store

We copy the data needed for a given flights-pipeline run from the Source-of-Truth GCS bucket `gs://contrails-301217-ecmwf-era5-zarr-v2/`.
For small runs, use `gcloud bucket cp` or `gsutil cp`, but for larger (many days/months), use the Google Cloud Storage Transfer Service. 
It is possible to set this up using the Google Cloud web UI or the scripted version in [copy_era5_gcs_to_staging.sh](copy_era5_gcs_to_staging.sh).

### Run the copy_era5_gcs_to_staging.sh script

The script takes 4 inputs: start_date, end_date, target_zarr_gcs_bucket, destination_zarr_gcs_bucket.

From a terminal set up and authenticated with `gcloud`, Run the script like this:

```shell
$ ./copy_era5_gcs_to_staging.sh 2024-12-31 2025-02-02 gs://contrails-301217-ecmwf-era5-zarr-v2/ gs://contrails-301217-ecmwf-era5-zarr-v2-staging/
```

And expect output like:

```shell
creationTime: '2026-03-13T16:23:15.521660281Z'
lastModificationTime: '2026-03-13T16:23:15.521660281Z'
loggingConfig: {}
name: transferJobs/transfer-2024-12-31-to-2025-02-02-1773418994
projectId: contrails-301217
schedule:
  scheduleEndDate:
    day: 13
    month: 3
    year: 2026
  scheduleStartDate:
    day: 13
    month: 3
    year: 2026
status: ENABLED
transferSpec:
  gcsDataSink:
    bucketName: contrails-301217-ecmwf-era5-zarr-v2-staging
  gcsDataSource:
    bucketName: contrails-301217-ecmwf-era5-zarr-v2
  objectConditions:
    includePrefixes:
    - 20241231_pl.zarr
    - 20241231_sl.zarr
    - 20250101_pl.zarr
    - 20250101_sl.zarr
    - 20250102_pl.zarr
    - 20250102_sl.zarr
    - 20250103_pl.zarr
    - 20250103_sl.zarr
    - 20250104_pl.zarr
    - 20250104_sl.zarr
    - 20250105_pl.zarr
    - 20250105_sl.zarr
    - 20250106_pl.zarr
    - 20250106_sl.zarr
    - 20250107_pl.zarr
    - 20250107_sl.zarr
    - 20250108_pl.zarr
    - 20250108_sl.zarr
    - 20250109_pl.zarr
    - 20250109_sl.zarr
    - 20250110_pl.zarr
    - 20250110_sl.zarr
    - 20250111_pl.zarr
    - 20250111_sl.zarr
    - 20250112_pl.zarr
    - 20250112_sl.zarr
    - 20250113_pl.zarr
    - 20250113_sl.zarr
    - 20250114_pl.zarr
    - 20250114_sl.zarr
    - 20250115_pl.zarr
    - 20250115_sl.zarr
    - 20250116_pl.zarr
    - 20250116_sl.zarr
    - 20250117_pl.zarr
    - 20250117_sl.zarr
    - 20250118_pl.zarr
    - 20250118_sl.zarr
    - 20250119_pl.zarr
    - 20250119_sl.zarr
    - 20250120_pl.zarr
    - 20250120_sl.zarr
    - 20250121_pl.zarr
    - 20250121_sl.zarr
    - 20250122_pl.zarr
    - 20250122_sl.zarr
    - 20250123_pl.zarr
    - 20250123_sl.zarr
    - 20250124_pl.zarr
    - 20250124_sl.zarr
    - 20250125_pl.zarr
    - 20250125_sl.zarr
    - 20250126_pl.zarr
    - 20250126_sl.zarr
    - 20250127_pl.zarr
    - 20250127_sl.zarr
    - 20250128_pl.zarr
    - 20250128_sl.zarr
    - 20250129_pl.zarr
    - 20250129_sl.zarr
    - 20250130_pl.zarr
    - 20250130_sl.zarr
    - 20250131_pl.zarr
    - 20250131_sl.zarr
    - 20250201_pl.zarr
    - 20250201_sl.zarr
    - 20250202_pl.zarr
    - 20250202_sl.zarr
Transfer job 'transfer-2024-12-31-to-2025-02-02-1773418994' created and started.
Files with prefixes from 2024-12-31 to 2025-02-02 will be copied from gs://contrails-301217-ecmwf-era5-zarr-v2/ to gs://contrails-301217-ecmwf-era5-zarr-v2-staging/.

Total transferred: 12 GB

```