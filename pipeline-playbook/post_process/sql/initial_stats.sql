-- count of total jobs (flights) output from the trajectory worker
SELECT COUNT(*)
FROM :inventory_summary_table;

-- count of total jobs (flights) output from the trajectory worker for the null-airline case
SELECT COUNT(*)
FROM :inventory_summary_table
WHERE airline_iata IS NULL;

-- count of dupes for non-null airlines; combination of normal dupes and airline_iata conflict
SELECT (COUNT(*) - (COUNT(DISTINCT(flight_id)))) AS dupe_count
FROM :inventory_summary_table
WHERE airline_iata IS NOT NULL;

-- count of false null airline iata flights that passed thru the TW
-- these are collisions between a true non-null airline iata flight (which we want to keep), and a false null flight (which we want to reject)
WITH aiata_per_fid_tb AS (SELECT flight_id, ARRAY_AGG(DISTINCT (IFNULL(airline_iata, "null"))) AS airline_iata_list
                          FROM :inventory_summary_table
                          GROUP BY flight_id),
     null_aiata_dupe_fid_tb AS (SELECT *
                                FROM aiata_per_fid_tb
                                WHERE ARRAY_LENGTH(airline_iata_list) > 1
                                  AND "null" IN UNNEST(airline_iata_list))
SELECT COUNT(*) AS false_null_flight_id_conflict_cnt
FROM null_aiata_dupe_fid_tb