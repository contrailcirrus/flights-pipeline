# Hyperdisk setup
Proof of concept work, attempting to use a hyperdisk durable/persistent storage 
for a read-many configuration, whereby many trajectory worker instances connect to
and read from a hyperdisk volume, that volume being populated with the zarr stores
used for the MetDataset xarray instances for running CoCiP.

# Steps

## Step 1 - hydrate a hyperdiskML instance
[Overview GCP Ref Docs](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml)


**(1) Create a custom k8s compute class for the GCS -> hyperdiskML sync job**
```bash
kubectl apply -f gcs-to-hyperdisk-compute-class.yaml
```
**(2) populate hyderdiskML instance with gcs zarr content**

[REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#transfer-data)

Create the `GCPDataSource` custom k8s resource, which defines the target GCS bucket for the volume-populator (hydration) job.
[REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#gcpdatasource)

```bash
kubectl apply -f gcs-era5-zarr-data-source.yaml
```
```text
⚠️ Only delete a `GCPDataSource` resource _after_ removing any `PersistentVolumeClaim`s referencing the `GCPDataSource`.
```

**(3) create a single-zone k8s StorageClass for the HyperdiskML**

[REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#create-storageclass)

```bash
kubectl apply -f hyperdiskml-useast1-storage-class.yaml
```
Note the `provisioned-throughput-on-create` parameter. 
To research: how do you modulate throughput after instantiation?

**(4) create a PersistentVolumeClaim for HyperdiskML**

[REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#create-pvc)

```bash
kubectl apply -f zarr-volume-populator-pvc.yaml
```

If the `VOLUMEBINDINGMODE` of the `storageClass` referenced in the PVC is set to `Immediate`,
then a data transfer job from the `GCSDataSource` referenced in the PVC will trigger immediately.
If the mode is set to `WaitForFirstConsumer`, however, then the data transfer won't start
until the first pod binds to the PVC.

To research: do we pay for the PVC/hyperdisk storage after the PVC is created, even if the binding mode is set to `WaitForFirstConsumer`?
Is the underlying persistent volume auto-created with we create the PVC, or on first binding of a pod 
(is the answer different depending on the binding mode). Will the underlying PV ever be destroyed, in either binding mode.
Are there any circumstances in which re-syncing with the GCSDataSource? (e.g. if casees where the PV is ever destroyed)

🔎 The data transfer job can be monitored. See [REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#view-data-transfer)
```bash
kubectl describe pvc era5-zarr-gcs-populator-job-pvc -n flights-pipeline-prod
```

## Use HyperDiskML PesistentVolumeClaim in a pod
Now, you can use the persistent volume claim in a job.

If you first want to verify the content sync'ed to the PVC, you can create a temporary pod.
[REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#create-pod)

(1) create a generic busybox pod, that is in infinite sleep.
```bash
kubectl apply -f inspector-pod.yaml
```

(2) tunnel into the pod and inspect the filesystem.
```bash
kubectl exec -it zarr-hyperdisk-inspector -n flights-pipeline-prod -- /bin/sh
## once connected to the pod with a shell...
cd /ecmwf-zarr-v2 && ls
```

## TearDown
The following steps are used to tear down the resources created above.

[REF](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-populator-hdml#clean-up)