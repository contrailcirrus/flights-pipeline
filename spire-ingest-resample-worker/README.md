# Spire Ingest Resample Worker

## Overview
A Kubernetes deployment that ingests a waypoints record from a pubsub subscription, 
and performs inward interpolation and backwards interpolation for missing waypoints, 
on a per flight-instance basis.

This service generates and writes to pubsub:
1) the 1Min resampled waypoints (to be injected into BigQuery) 
2) flight segments (a tuple with three temporally contiguous 1Min sampled waypoints) 
   to be consumed by a Cocip worker

# Behavior
This service consumes a waypoints record from pubsub.
A waypoints record is a list of waypoints spanning 
a fixed time window (time being on event time, aka `timestamp`).
A waypoints record object belongs to a  single flight instance (icao address).
The record includes the first and last waypoint, if available, 
in each minute interval of the window.

This service first does inward interpolation (intra-record interpolation), 
interpolating to the minute within the window.

THis service then does backward interpolation (inter-record interpolation), 
interpolates to the minute backward to the last known waypoint for the flight instance.

In order to perform the backward interpolation, 
this service checks a remote datastore for the last known waypoint for the flight instance.

Lastly, the Resample Worker will generate flight segment tuples 
from the contiguous 1Min waypoints.

## Environment Variables
The following environment variables are expected for production and development environments.

| name                                   |                               description                                |
|:---------------------------------------|:------------------------------------------------------------------------:|
| SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID |     fully-qualified uri for the waypoints record pubsub subscription     |
| SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID      |        fully-qualified uri for the pubsub topic that writes to BQ        |
| SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID  | fully-qualified uri for the pubsub topic that writes raw waypoints to BQ |
| TRAJECTORY_CHUNK_TOPIC_ID              |    fully-qualified uri for the flights trajectory chunk pubsub topic     |
| REDIS_HOST                             |                    ipv4 address of the redis instance                    |
| REDIS_PORT                             |                       port for the redis instance                        |
| LOG_LEVEL                              |                log level for service in cloud environment                |**

### Prerequisites

- **Google Cloud CLI**: Download and set up the [gcloud CLI](https://cloud.google.com/sdk/gcloud/)
- **kubectl CLI**: Download and set up as per [these instructions](https://github.com/contrailcirrus/sre/tree/main/kubernetes#developer-setup)
- **Python3.12**: This application currently runs on [Python3 v3.12]((https://www.python.org/downloads/))
- [pipenv](https://pipenv.pypa.io/en/latest/installation.html): For dependencies
- **Docker**: If you plan to dockerize the application locally, install the latest version of
[Docker](https://www.docker.com/) or [podman](https://podman.io/).
(See also [use podman in a rootless environment](https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md))

### Setup

#### Pipenv

This project uses Pipenv to manage dependencies.

`make prod-install` will install, from the lock file, all the dependencies needed for running the application in production.

`make dev-install` will install, from the lock file, all prod dependencies plus additional dev dependencies.

`make activate` will (in your current shell) activate the virtual environment and source variables defined in your `.env` file.

If you are not familiar with Pipenv tooling, please familiarize yourself with the [basics](https://pipenv-es.readthedocs.io/es/stable/basics.html), and how to use the [pipenv CLI](https://pipenv.pypa.io/en/latest/cli.html).

#### environment variables

If you want to run the app localhost, you will need to specify the environment variables listed in
the [Environment Variables, Dev](#dev) section above.

Specify the environment variables in a `.env` file, in the root of the project directory,
as a newline delimited list.

e.g.

```bash
# .env
VAR_1=""
VAR_2=""
```

Use Pipenv to automatically load env vars in your bash shell's environment.

e.g

```bash
make activate  # activate the pipenv virtual environment for the current terminal shell
echo $VAR_1  # variables in your .env are sourced to the shell
python -m myapp.py  # env vars are accessible to application
```

#### redis access

If you plan to connect to the remote redis instance from localhost, you will need to:
1) create a GCP Compute Engine VM
2) use the VM to establish a tunnel between localhost > VM (in VPC) > redis

Follow these steps (don't forget to clean up your VM after use!).
```bash
gcloud compute instances create SOME_VM_NAME --machine-type=f1-micro --zone=us-east1-b
REDIS_HOST=REMOTE_HOST_IPV4 && REDIS_PORT=6379 && gcloud compute ssh SOME_VM_NAME --zone=us-east1-b -- -N -L $REDIS_PORT:$REDIS_HOST:$REDIS_PORT
```

## Deploy
### Infrastructure
Terraform is used for creating, managing and configuring Cloud infra.
See the terraform files defined in the [.cloud](.cloud) directory.
Terraform maintains a [backend state file in GCS](.cloud/main.tf), 
used as a source of truth for the currently deployed state of Cloud resources.

Running `terraform plan` in the `.cloud` directory will outline proposed changes.
Terraform will outline a "plan" for additions, modifications or deletions, by comparing the local 
`*.tf` files with the remote state file.

Running `terraform apply` will apply these changes to the Cloud resources,
thereby harmonizing the state of all three:
1. deployed resources 
2. backend state file
3. state as defined locally in `*tf`

## CICD
Merges to `develop` will deploy (docker build, docker push, k8s deploy) 
the application to the dev cloud environment.

Merges to `main` will deploy (docker build, docker push, k8s deploy) 
the application to the prod cloud environment.


