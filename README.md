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
    subgraph k8s_3[Kubernetes]
        trajectory_worker_rt(dep: trajectory-worker-realtime)
        trajectory_worker_gaia(dep: trajectory-worker-gaia, aka. FER)
    end
    style k8s_3 fill:#C88908
    subgraph k8s_4[Kubernetes]
        fer_cron(cron: flight emissions report)
    end
    style k8s_4 fill:#C88908
    subgraph redis1[Redis]
        resample_worker_cache(resample-worker-cache)
    end
    style redis1 fill:#03ab52
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
    subgraph pub_sub5[PubSub]
        traj_worker_rt_chunk_topic(traj-worker-rt-chunk-topic)
        traj_worker_rt_chunk_sub(traj-worker-rt-chunk-sub)
        traj_worker_rt_chunk_5xop[5x]:::operationStyle
        traj_worker_rt_chunk_deadletter(traj-worker-rt-chunk-deadletter)
    end
    style pub_sub5 fill:#0864C8
    subgraph pub_sub6[PubSub]
        traj_worker_gaia_chunk_topic(traj-worker-rt-gaia-topic)
        traj_worker_gaia_chunk_sub(traj-worker-gaia-chunk-sub)
        traj_worker_gaia_chunk_5xop[5x]:::operationStyle
        traj_worker_gaia_chunk_deadletter(traj-worker-gaia-chunk-deadletter)
    end
    style pub_sub6 fill:#0864C8
    subgraph pub_sub7[PubSub]
        traj_worker_cocip_bq_topic(traj-worker-cocip-bq-topic)
        traj_worker_cocip_bq_sub(traj-worker-cocip-bq-sub)
        traj_worker_cocip_bq_15xop[15x]:::operationStyle
        traj_worker_cocip_bq_deadletter(traj-worker-cocip-bq-deadletter)
    end
    style pub_sub7 fill:#0864C8
    subgraph bigquery1[BigQuery]
        spire_flights_raw_tb(table: spire-flights-raw)
    end
    style bigquery1 fill:#f030d9
    subgraph bigquery2[BigQuery]
        spire_flights_resampled_tb(table: spire-flights-resampled)
    end
    style bigquery2 fill:#f030d9
    subgraph bigquery3[BigQuery]
        trajectory_cocip_tb(table: trajectory-cocip)
    end
    style bigquery3 fill:#f030d9
    %% flow/associations
    spire_api --> spire_ingest_api_scraper
    spire_ingest_api_scraper --> spire_ingest_api_topic
    spire_ingest_api_scraper --> spire_ingest_raw_bq_topic
    spire_ingest_api_topic --> spire_ingest_api_sub
    
    spire_ingest_api_sub --> spire_ingest_resample_worker
    spire_ingest_resample_worker --> spire_ingest_raw_bq_topic
    spire_ingest_resample_worker --> spire_ingest_resample_bq_topic
    spire_ingest_resample_worker --> traj_worker_rt_chunk_topic
    spire_ingest_raw_bq_topic --> spire_ingest_raw_bq_sub
    spire_ingest_resample_bq_topic --> spire_ingest_resample_bq_sub
    
    spire_ingest_resample_worker <--> resample_worker_cache
    
    spire_ingest_raw_bq_sub --> spire_flights_raw_tb
    spire_ingest_resample_bq_sub --> spire_flights_resampled_tb
    
    
    spire_ingest_api_sub -.- api_scraper_5xop
    api_scraper_5xop -.-> spire_ingest_api_sub_deadletter
    
    spire_ingest_raw_bq_sub -.- bq_raw_10xop
    bq_raw_10xop -.-> spire_ingest_raw_bq_sub_deadletter
    
    spire_ingest_resample_bq_sub -.- bq_resample_10xop
    bq_resample_10xop -.-> spire_ingest_resample_bq_sub_deadletter
    
    traj_worker_rt_chunk_topic --> traj_worker_rt_chunk_sub
    traj_worker_rt_chunk_sub -.- traj_worker_rt_chunk_5xop
    traj_worker_rt_chunk_5xop -.- traj_worker_rt_chunk_deadletter
    
    traj_worker_rt_chunk_sub --> trajectory_worker_rt
    
    traj_worker_gaia_chunk_topic --> traj_worker_gaia_chunk_sub
    traj_worker_gaia_chunk_sub -.- traj_worker_gaia_chunk_5xop
    traj_worker_gaia_chunk_5xop -.- traj_worker_gaia_chunk_deadletter
    
    fer_cron --> traj_worker_gaia_chunk_topic
    
    traj_worker_gaia_chunk_sub --> trajectory_worker_gaia
    
    trajectory_worker_gaia --> traj_worker_cocip_bq_topic
    trajectory_worker_rt --> traj_worker_cocip_bq_topic
    
    traj_worker_cocip_bq_topic --> traj_worker_cocip_bq_sub
    traj_worker_cocip_bq_sub -.- traj_worker_cocip_bq_15xop
    traj_worker_cocip_bq_15xop -.- traj_worker_cocip_bq_deadletter
    
    traj_worker_cocip_bq_sub --> trajectory_cocip_tb
```