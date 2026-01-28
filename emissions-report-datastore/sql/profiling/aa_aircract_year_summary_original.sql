WITH airline_aggs AS (
    SELECT
        v.airline_iata,
        COUNT(v.flight_id) AS flight_cnt,
        SUM(v.sum_ef_mj) AS total_ef_mj,
        SUM(v.chunk_len_km) AS total_len_km,
        (SUM(v.sum_ef_mj) / NULLIF(SUM(v.chunk_len_km), 0)) AS avg_ef_mj_per_km
    FROM "trajectory-cocip" v
    WHERE
        v.time_start >= '2024-01-01' AND v.time_end <= '2024-12-31'
        AND v.engine_uid IN ('01P08CM105')
        AND v.aircraft_type_icao IN ('A333', 'A320')
    GROUP BY
        v.airline_iata
),
windowed_stats AS (
    SELECT
        airline_aggs.*,
        AVG(airline_aggs.avg_ef_mj_per_km) OVER () AS global_avg_ef_mj_per_km,
        SUM(airline_aggs.total_ef_mj) OVER () AS global_sum_ef_mj,
        RANK() OVER (ORDER BY airline_aggs.avg_ef_mj_per_km DESC) AS impact_rank,
        COUNT(*) OVER () AS total_airlines_cnt,
        SUM(airline_aggs.total_len_km) OVER () AS global_len_km,
        SUM(airline_aggs.flight_cnt) OVER () AS global_flight_cnt
    FROM airline_aggs
)
SELECT
    flight_cnt,
    total_ef_mj,
    total_len_km,
    avg_ef_mj_per_km,
    global_avg_ef_mj_per_km,
    global_sum_ef_mj,
    impact_rank,
    total_airlines_cnt,
    global_len_km,
    global_flight_cnt
FROM windowed_stats
WHERE airline_iata = 'AA';