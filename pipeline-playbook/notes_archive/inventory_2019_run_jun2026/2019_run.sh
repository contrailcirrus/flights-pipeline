# bash command executed on VM to iterate thru & submit all job_id based TWJDs to the TWJF queue
# e.g. ./cli.py jobworker submit -j e82cc9c159f67a8fb58aa533d40dd0a4 -l inventory_2019_run_jun2026_jobs -w gcs -s era5 -t

cat 2019_job_id_list.txt | xargs -I % ./cli.py jobworker submit -j % -l inventory_2019_run_jun2026_jobs -w gcs -s era5 -t > 2019_run.log 2>&1
