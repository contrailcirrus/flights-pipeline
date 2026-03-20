# Hyperdisk setup
Proof of concept work, attempting to use a hyperdisk durable/persistent storage 
for a read-many configuration, whereby many trajectory worker instances connect to
and read from a hyperdisk volume, that volume being populated with the zarr stores
used for the MetDataset xarray instances for running CoCiP.

# Steps

## Pre-work

(1) create a custom k8s `ComputeClass` resource, that is used by the auto-magical hyperdisk populator.
_This only needs to be done once, should not be torn-down, and is a cluster-wide resource_.
```shell
kubectl apply -f gcs-to-hyperdisk-compute-class.yaml
```

If you are not sure if this has been run, check with e.g. 
```shell
$ kubectl get computeclass | grep gcs-to-hdml
gcs-to-hdml-compute-class   16d
```

(2) create a custom k8s `StorageClass` resource, that defines the relationship of k8s to the underlying
HyperdiskML GCP Disk resource.
_This only needs to be done once, should not be torn-down, and is a cluster-wide resource_.
```shell
kubectl apply -f hyperdiskml-useast1-storage-class.yaml
```


Notes:
- the underlying HyperdiskML disk (viewable in `GCP Compute Engine > Disks`) is automatically provisioned when a k8s PVC is created using this `StorageClass`.
- we can redefine this `StorageClass`, if we want a different HyderdiskML throughput value applied on-create of the Hyperdisk ML
- we can redefine this `StorageClass`, if we want to have HyperDiskML disk instances created in multiple regions
- with `volumeBindingMode: Immediate`, a kubernetes Persistent Volume (`PV`) is automatically provisioned when we create the k8s PersistentVolumeClaim (`PVC`)


## Step 0 - stage zarr stores
First, copy the zarr stores we want on the Hyperdisk into a separate GCS Bucket. See [pre-processing instructions](pipeline-playbook/pre_process/README.md) on how to get appropriate Met data zarr stores into a GCS Bucket.
This Bucket is our staging ground for the zarr stores we plan to sync to the HyperdiskML instance.

## Step 1 - create a `GCSDataSource` resource

First, modify `gcs-era5-zarr-data-source.yaml` to point to the GCS bucket from Step 0.

Next, create the `GCPDataSource` custom k8s resource.
[REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#gcpdatasource)
This is a namepsace-level resource.

```bash
kubectl apply -f gcs-era5-zarr-data-source.yaml -n flights-pipeline-<dev/prod>
```
```text
⚠️ Only delete a `GCPDataSource` resource _after_ removing any `PersistentVolumeClaim`s referencing the `GCPDataSource`.
```

If you want to check if there is a GCS DataSource available, check with e.g. 

```shell
kubectl get gcpdatasource --namespace=flights-pipeline-<dev/prod>
```

## Step 2 - create a `PersistentVolumeClaim` (and hydrate a hyperdiskML instance)

First, create a PersistentVolumeClaim resource in k8s, which creates a claim to the HyperdiskML `StorageClass` resource,
and references the `GCPDataSource` resource from Step 1. Make sure the size of this disk is set appropriately to hold the contents in the GCS Bucket being copied into it. Use Cloud Console Monitoring or `gsutil du` to get the bucket size (Monitoring is cheaper for very large buckets).

[REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#create-pvc)
_This is a namespace-level resource_.
```bash
kubectl apply -f era5-zarr-gcs-pvc.yaml -n flights-pipeline-<dev/prod>
```

Next, monitor the creating of the `PVC` with `kubectl describe pvc <name-of-pvc> -n flights-pipeline-<dev/prod>`.
See [REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#view-data-transfer)
The `PVC` will be in a `PENDING` state while the HyperdiskML disk is provisioned, and data from bucket in Step 0
is copied to the disk.
It may take several hours for data to sync from the bucket.
If all goes well and the sync job succeeds, the `PVC` instance will show up as `READY` in k8s.

### Background: Automatic Provisioning of the HyperdiskML disk & k8s PersistentVolume
When this `PVC` is created, it automatically provisions the HyperdiskML disk instance (viewable in the GCP Console, under Compute Engine > Disks).
When this `PVC` is created, the underlying kubernetes `PV` linking the `PVC` to the HyperdiskML instance is also created automatically.

Note that if the `VolumeBindingMode` of the `StorageClass` resource referenced in the `PVC` is set to `WaitForFirstConsumer` instead of `Immediate`,
then this auto-provisioning of the `PV` and `HyperdiskML` disk instance doesn't kick-off until the first occurrence of a pod binding to the `PVC`.

### Background: Automatic Provisioning of the Hyperdisk Volume Populator Job
The presense of the `dataSourceRef` key in the `PVC` kicks off some GKE automagic.
After the PVC is created, a separate k8s `Job` is also kicked off, which runs the background process for sync'ing the GCS bucket from Step 0 to the HyperdiskML disk instance.

### Utils: Inspect the HyperdiskML disk content
The best way to inspect the file system of the HyperdiskML disk is to create and ssh into a pod.
For example, deploy `inspector-pod.yaml` to the namespace with the `PVC` created in this step.
Then:
```bash
kubectl exec -it zarr-hyperdisk-inspector -n flights-pipeline-<dev/prod> -- /bin/sh
## once connected to the pod with a shell...
cd /ecmwf-zarr-v2 && ls
```

## Step 3 - Use HyperDiskML PesistentVolumeClaim in the TrajectoryWorker
Now, you can use the persistent volume claim in the TrajectoryWorker, and give
the TW direct access to the HyperdiskML's content.

First, add a `volume` and `volumeMount` definition to the pod spec for the TW,
referencing the `PVC` resource from Step 2, and mounting the HyperdiskML instance
to a path in the pod.
```yaml
spec:
  containers:
  - ...
    volumeMounts:
      - mountPath: /ecmwf-zarr-v2
        name: ecmwf-zarr-v2
  volumes:
    - name: ecmwf-zarr-v2
      persistentVolumeClaim:
        claimName: era5-zarr-gcs-pvc
```

Next, update the environment variable for the TW GithUb deployment, to point to the 
local filepath for the ERA5 zarr stores.
```yaml
trajectory-worker-deploy-<dev/prod>.yaml
  - name: Deploy helm resources
    working-directory: trajectory-worker/helm
    run: make deploy
    env:
#          ERA5_SOURCE_PATH: gs://contrails-301217-ecmwf-era5-zarr-v2
      ERA5_SOURCE_PATH: /ecmwf-zarr-v2
    ...
```

## TearDown
[REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#clean-up)
We pay for the HyperdiskML instance and the storage of the zarr stores in the staging
bucket from Step 0.

To tear down these resources when not in use:
- redeploy the TrajectoryWorker, _commenting-out/removing the `volumes` and `volumesMount` from the pod spec.
- confirm that the TW has been redeployed, and no pods (in dev or prod) are bound to the `PVC` from Step 2
- delete the `PVC` resource created in step 2
- (optional) delete the `GCSDataSource` created in step 1 (only do this after k8s has finished removing the `PVC`)

