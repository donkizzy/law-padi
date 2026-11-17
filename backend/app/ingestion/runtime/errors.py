class IngestionWorkerError(RuntimeError):
    pass


class IngestionLeaseLost(IngestionWorkerError):
    pass
