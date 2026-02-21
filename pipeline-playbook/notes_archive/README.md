# Notes Archive
A directory holding notes from large pipeline runs.

Notes from a given "run" are in a subdirectory, of format: `inventory_{flight_date_range}_run_{pipeline_run_time}`.
1. `flight_date_range` and indicator of the flight date range included in the run. 
e.g. `2024` would be all global flights, where take-off time was in the 2024 calendar year.
It may happen that a pipeline run only covers e.g. some airlines. In this case, a good descriptor
in this field would be `2024_partial`, with a description of the actual run specs in the subdirectory's readme.
2. `pipeline_run_time` a designator to indicate approx. when the pipeline run took place.
