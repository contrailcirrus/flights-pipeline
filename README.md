# Flights Pipeline
This mono-repo holds infra & multiple services for the flights processing pipeline.
Each service is managed and deployed independently.
The service topology, constituting the overall flights pipeline, is outlined here.

```mermaid
---
title: Flights Pipeline
---
graph 
    %% style
    classDef operationStyle fill:#8f8e8c, stroke-dasharray: 5 5
    %% operations
    raw_push_op[push operation]:::operationStyle

    %% services/processes
    spire_api(Spire API)
    subgraph cloud_scheduler[CloudScheduler]
        spire_cron[Spire CRON \n */5 * * * *]
    end
    style cloud_scheduler fill:#0f7364
    subgraph cloud_functions[CloudFunctions]
        spire_ingest_job_publisher(spire-ingest-job-publisher)
    end
    style cloud_functions fill:#C88908
    subgraph pub_sub[PubSub]
        spire_ingest_job_topic(spire-ingest-job-topic)
        ordered_queue_op[ordered]:::operationStyle
        spire_ingest_job_subscription(spire-ingest-job-sub)
    end
    style pub_sub fill:#0864C8
    subgraph kubernetes[Kubernetes]
        spire_ingest_api_scraper(spire-ingest-api-scraper)
    end
    style kubernetes fill:#a82ca6
    %% flow/associations
    spire_cron --> raw_push_op
    raw_push_op --> spire_ingest_job_publisher
    spire_ingest_job_publisher --> spire_ingest_job_topic
    spire_ingest_job_topic --> ordered_queue_op
    ordered_queue_op --> spire_ingest_job_subscription
    spire_ingest_job_subscription --> spire_ingest_api_scraper
    spire_api --> spire_ingest_api_scraper
```