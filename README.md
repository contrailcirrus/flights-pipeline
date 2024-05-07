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

    %% services/processes
    spire_api(Spire API)
    subgraph k8s_1[Kubernetes]
        spire_ingest_api_scraper(cron: spire-ingest-api-scraper)
    end
    style k8s_1 fill:#C88908
    subgraph k8s_2[Kubernetes]
        spire_ingest_resample_worker(dep: spire-ingest-resample-worker)
    end
    style k8s_2 fill:#C88908
    subgraph pub_sub1[PubSub]
        spire_ingest_api_topic(spire-ingest-api-topic)
        spire_ingest_api_sub(spire-ingest-api-sub)
        api_scraper_5xop[5x]:::operationStyle
        spire_ingest_api_sub_deadletter(api-scraper-deadletter)
    end
    style pub_sub1 fill:#0864C8
    subgraph pub_sub2[PubSub]
    spire_ingest_raw_bq_topic(spire-ingest-raw-bq-topic)        
        spire_ingest_raw_bq_sub(spire-ingest-raw-bq-sub)
        bq_raw_10xop[10x]:::operationStyle
        spire_ingest_raw_bq_sub_deadletter(bq-raw-deadletter)    
    end
    style pub_sub2 fill:#0864C8
    subgraph pub_sub3[PubSub]
        spire_ingest_resample_bq_topic(spire-ingest-resample-bq-topic)
        spire_ingest_resample_bq_sub(spire-ingest-resample-bq-sub)
        bq_resample_10xop[10x]:::operationStyle
        spire_ingest_resample_bq_sub_deadletter(bq-resample-deadletter)
    end
    style pub_sub3 fill:#0864C8
    subgraph pub_sub4[PubSub]
        spire_ingest_resample_bq_topic(spire-ingest-resample-bq-topic)
        spire_ingest_resample_bq_sub(spire-ingest-resample-bq-sub)
        bq_resample_10xop[10x]:::operationStyle
        spire_ingest_resample_bq_sub_deadletter(bq-resample-deadletter)
        flight_trajectory_rt_topic(flight-trajectory-realtime-topic)
        flight_trajectory_rt_sub(flight-trajectory-realtime-sub)
        flight_trajectory_rt_2xop[2x]:::operationStyle
        flight_trajectory_rt_sub_deadletter(flight-trajectory-realtime-deadletter)
    end
    style pub_sub4 fill:#0864C8
    subgraph bigquery1[BigQuery]
        spire_flights_raw_tb(table: spire-flights-raw)
    end
    style bigquery1 fill:#f030d9
    subgraph bigquery2[BigQuery]
        spire_flights_resampled_tb(table: spire-flights-resampled)
    end
    style bigquery2 fill:#f030d9
    %% flow/associations
    spire_api --> spire_ingest_api_scraper
    spire_ingest_api_scraper --> spire_ingest_api_topic
    spire_ingest_api_scraper --> spire_ingest_raw_bq_topic
    spire_ingest_api_topic --> spire_ingest_api_sub
    spire_ingest_api_sub --> spire_ingest_resample_worker
    spire_ingest_resample_worker --> spire_ingest_raw_bq_topic
    spire_ingest_resample_worker --> spire_ingest_resample_bq_topic
    spire_ingest_resample_worker --> flight_trajectory_rt_topic
    spire_ingest_raw_bq_topic --> spire_ingest_raw_bq_sub
    spire_ingest_resample_bq_topic --> spire_ingest_resample_bq_sub
    flight_trajectory_rt_topic --> flight_trajectory_rt_sub
    
    spire_ingest_raw_bq_sub --> spire_flights_raw_tb
    spire_ingest_resample_bq_sub --> spire_flights_resampled_tb
    
    
    spire_ingest_api_sub -.- api_scraper_5xop
    api_scraper_5xop -.-> spire_ingest_api_sub_deadletter
    
    spire_ingest_raw_bq_sub -.- bq_raw_10xop
    bq_raw_10xop -.-> spire_ingest_raw_bq_sub_deadletter
    
    spire_ingest_resample_bq_sub -.- bq_resample_10xop
    bq_resample_10xop -.-> spire_ingest_resample_bq_sub_deadletter
    
    flight_trajectory_rt_sub -.- flight_trajectory_rt_2xop
    flight_trajectory_rt_2xop -.- flight_trajectory_rt_sub_deadletter
```