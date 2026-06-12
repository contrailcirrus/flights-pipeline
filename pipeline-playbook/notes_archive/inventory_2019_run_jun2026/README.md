# Inventory 2019 (run: June 2026)

## GKE Standard Cluster Setup

We set up a new standard GKE cluster for Trajectory Worker pods to run in a configuration where we can better control the available resources and size of the node instances to better match CPU/Memory resources with VM bandwidth and total number of connections to the Hyperdisk-ML disk.

Based on new availability of bandwidth allocation from GCP, we have Hyperdisk-ML bandwidth availability up to 250GiB/s in `us-east4-a` and `us-east4-c`. We set up the new cluster in `us-east4-c` and will set up the Hyperdisk-ML in the same zone.

To set up the new cluster, we made a new `kubernetes-standard` subdirectory in the [sre repo](https://github.com/contrailcirrus/sre/tree/main/kubernetes-standard) which has a `.cloud` subdirectory holding relevant Terraform configuration to set up thew new cluster with its state saved under its own prefix in our GCS bucket that holds our terraform state files. The README there also describes how to set up the cluster. In short, it sets up a new GKE cluster in `us-east4` using zones `a` and `c`. It sets up the necessary workload identity configuration to allow nodes to access GCP resources, sets up `flights-pipeline-dev` and `flights-pipeline-prod` namespaces, and sets up a metrics server adapter to allow horizontal scaling based on PubSub metrics. The new cluster is named `contrails-gke-general-std-useast4`.

## Data setup

### Spire data
The 2019-2023 Spire data were merged into the source-of-truth Spire database BQ table `contrails-301217.flights_pipeline_prod.spire_flights_raw_prod`. The process was described in an internal repo [here](https://github.com/contrailcirrus/developer-sandbox/blob/a467ed9a7a377e1fc1fcc8c7361e7f3cd80f5274/spire-backfill-2019-2021-imperial-spire-adsb-etl/README.md), with callsighn patches documented [here](https://github.com/contrailcirrus/developer-sandbox/blob/a467ed9a7a377e1fc1fcc8c7361e7f3cd80f5274/spire-callsign-patch-2022-2023/README.md). The GCS Spire Parquet file cache was "warmed" for 2019-2023 flights, ensuring we could run the flights-pipeline from the GCS cache instead of the BQ table.

### Hyperdisk-ML Met Data
First removed all files from the existing Met zarr store which is used as the basis for what gets copied onto the Hyperdisk by setting a new Lifecycle rule. After the data were removed, I removed the 0-day file removal lifecycle policy.

Once the destination bucket was empty, I copied the data over using the [copy_era5_gcs_to_staging.sh](../../pre_process/copy_era5_gcs_to_staging.sh) script with the command:

```shell
./copy_era5_gcs_to_staging.sh 2019-01-01 2020-01-01 gs://contrails-301217-ecmwf-era5-zarr-v2/ gs://contrails-301217-ecmwf-era5-zarr-v2-staging/
```

The transfer copied 3886 GB of ERA5 met data to the Met zarr store bucket.

Note that this starts at the desired run start date 2019-01-01 instead of the day before 2018-12-31 to cover 
flights that cross the day boundary, though data from earlier than the desired start date may not really be necessary - we've just done that in the past.

#### Setting up the Hyperdisk
We have newly updated Hyperdisk-ML quotas and provisioned hardware enough to support 250GB/s in each `us-east4-a` and `us-east4-c`. We're updating to using those - trying first in `us-east4-c`.
I followed the [hyperdisk setup instructions](../../pre_process/hyperdisk-setup/README.md) to set up the hyperdisk. First, IO verified that the ComputeClass is set up: `kubectl get computeclass | grep gcs-to-hdml`. The StorageClass had startup bandwith set to 2400MB/s. We want to make sure the startup bandwidth is as low as it can be, so the user can select the appropriate bandwidth after creation (I think it can only be increased after creation). Created a new us-east4c hyperdisk storage class, set to 600MB/s, which is a bit above the minimum for a 4TiB Hyperdisk-ML disk, setting the zone to `us-east4-c` then applying: 

```shell
kubectl apply -f hyperdiskml-useast4c-storage-class.yaml
```

Checked that the GCPDataSource existed and was set up pointing to the correct GCS bucket:

```shell
kubectl get gcpdatasource --namespace=flights-pipeline-prod
  NAME                       AGE
  gcs-era5-zarr-datasource   62d
kubectl describe gcpdatasource gcs-era5-zarr-datasource --namespace=flights-pipeline-prod 
  Name:         gcs-era5-zarr-datasource
  Namespace:    flights-pipeline-prod
  Labels:       <none>
  Annotations:  <none>
  API Version:  datalayer.gke.io/v1
  Kind:         GCPDataSource
  Metadata:
    Creation Timestamp:  2026-03-17T19:51:03Z
    Generation:          1
    Resource Version:    1773777063225135011
    UID:                 414db58a-1629-429b-9506-36d4b4246bc3
  Spec:
    Cloud Storage:
      Service Account Name:  flights-pipeline-default-sa
      Uri:                   gs://contrails-301217-ecmwf-era5-zarr-v2-staging/
  Events:                    <none>
```

Creating a `PersistentVolumeClaim` by creating a new `era5-zarr-gcs-pvc-useast4c.yaml` file setting `resources:requests:storage` value to 4000Gi and referencing the us-east4 StorageClass, then applying with:

```shell
kubectl apply -f era5-zarr-gcs-pvc-useast4c.yaml -n flights-pipeline-prod
  persistentvolumeclaim/era5-zarr-gcs-pvc-useast4c created
```

And checking on status...

```shell
kubectl describe pvc era5-zarr-gcs-pvc-useast4c -n flights-pipeline-prod
  Name:          era5-zarr-gcs-pvc-useast4c
  Namespace:     flights-pipeline-prod
  StorageClass:  hyperdisk-ml-single-zone-useast4c
  Status:        Pending
  Volume:        
  Labels:        <none>
  Annotations:   volume.beta.kubernetes.io/storage-provisioner: pd.csi.storage.gke.io
                volume.kubernetes.io/storage-provisioner: pd.csi.storage.gke.io
  Finalizers:    [kubernetes.io/pvc-protection gkevolumepopulator/populate-target-protection]
  Capacity:      
  Access Modes:  
  VolumeMode:    Filesystem
  DataSource:
    APIGroup:  datalayer.gke.io
    Kind:      GCPDataSource
    Name:      gcs-era5-zarr-datasource
  Used By:     <none>
  Events:
    Type    Reason                Age                     From                                                                                              Message
    ----    ------                ----                    ----                                                                                              -------
    Normal  Provisioning          3m29s (x18 over 3h56m)  pd.csi.storage.gke.io_gke-51ae8619d7bb4843b683-301d-63a0-vm_52d9f16b-d1c4-4747-ab9f-1febfb18ed47  External provisioner is provisioning volume for claim "flights-pipeline-prod/era5-zarr-gcs-pvc-useast4c"
    Normal  Provisioning          3m29s (x18 over 3h56m)  external-provisioner                                                                              Assuming an external populator will provision the volume
    Normal  ExternalProvisioning  102s (x945 over 3h56m)  persistentvolume-controller                                                                       Waiting for a volume to be created either by the external provisioner 'pd.csi.storage.gke.io' or manually by the system administrator. If volume creation is delayed, please verify that the provisioner is running and correctly registered.
    Normal  TransferInProgress    0s (x79 over 3h53m)     gkevolumepopulator-populator                                                                      populateCompleteFn: For PVC era5-zarr-gcs-pvc-useast4c in namespace flights-pipeline-prod, transfer job in zone us-east4-c with request ID populator-job-69388a35-bf9f-4ff2-afb0-276450945ad1 is still active with pod status as - Phase: Running
  ```

I can also see the job and pod handling the data transfer, and the volume created to house the data transfer shows fairly high bandwidth (~100MiB/s) use.


## Job ID compilation
The 2019 run was executed using the new `job_id` based batching for the TWJDs/TWJF.

The job table was built with the following query (holding batches of ~1,000 flights).

NOTE THAT WE DON'T INCLUDE FLIGHTS ORIGINATING ON THE FIRST DAY OF 2019.

```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_2019_run_jun2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2019-01-01T00:00:00" AND "2019-12-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2019-01-02T00:00:00"),
     job_grp_tb AS (SELECT *,
                           SUBSTR(TO_HEX(SHA256(CONCAT(
                                   CAST(CAST(0.001 * ROW_NUMBER() OVER (PARTITION BY day_bin ORDER BY min_ts) AS INT64) AS STRING),
                                   CAST(day_bin AS STRING)))), 1, 32) AS job_id
                    FROM target_tb),
     agg_tb AS (SELECT job_id,
                       ARRAY_AGG(day_bin)   AS day_bin_arr,
                       ARRAY_AGG(flight_id) AS flight_id_list
                FROM job_grp_tb
                GROUP BY job_id)
SELECT job_id, FORMAT_DATE('%Y-%m-%d', ARRAY_FIRST(day_bin_arr)) AS day, flight_id_list
FROM agg_tb
```
