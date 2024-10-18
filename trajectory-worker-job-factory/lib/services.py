from lib.schemas import TrajectoryWorkerJobDescriptor
from lib.handlers import PubSubPublishHandler, BigQueryHandler


class TrajectoryBuilderSvc:
    """
    Service wrapper for building and submitting trajectory worker jobs (`WaypointsRecord`)
    to the trajectory worker job queue.
    """

    def __init__(
        self, bq_handler: BigQueryHandler, job_out_handler: PubSubPublishHandler
    ):
        self._bq_handler = bq_handler
        self._job_out_handler = job_out_handler

    def run(self, tjwd: TrajectoryWorkerJobDescriptor):
        return
