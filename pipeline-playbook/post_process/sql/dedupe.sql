-- STEP 1
-- drop any false null airline iata rows
DELETE
FROM :inventory_summary_table
WHERE flight_id IN (SELECT flight_id
                    FROM (SELECT flight_id,
                                 ARRAY_AGG(DISTINCT (IFNULL(airline_iata, "null"))) AS airline_iata_list
                          FROM :inventory_summary_table
                          GROUP BY flight_id)
                    WHERE ARRAY_LENGTH(airline_iata_list)
                        > 1
                      AND "null" IN UNNEST(airline_iata_list))
  AND airline_iata IS NULL


-- STEP 2
-- drop any other dupes
-- (this includes normal dupes, and randomly dropping any airline iata conflict dupes)
CREATE OR REPLACE TABLE :inventory_summary_table AS (SELECT *
                                                     FROM :inventory_summary_table
                                                     QUALIFY ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY _processed_at DESC) = 1);

