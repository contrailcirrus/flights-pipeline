class PermanentFailureException(Exception):
    """
    General exception indicating a failure that would not be remediated with retries.
    """


class InvalidQueryException(Exception):
    """
    Exception indicating that a query or request is invalid.
    """


class BadTrajectoryException(Exception):
    """
    Exception indicating a trajectory (flight instance) is invalid.
    """


class SpireCacheTooSmallException(Exception):
    """
    Exception indicating issue with content size of GCS Spire cache (/hourly/<some-cache-time>/*.pq)
    """


class BadJobIdLookupException(Exception):
    """
    Exception indicating that a bad lookup occurred in the lookup table for a given job id.
    """


class MalformedLookupTableException(Exception):
    """
    Exception indicating that the job_id lookup table is malformed (missing required cols).
    """
