class PermanentJobError(Exception):
    """The job can never succeed (bad input); dead-letter it immediately."""
