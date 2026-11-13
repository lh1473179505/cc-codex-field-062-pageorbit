def run_sync(args) -> int:
    raise NotImplementedError(
        "sync is not implemented. Handle page/cursor/Link pagination, truncated page resume, "
        "429 retry, schema drift qty->quantity, watermark and deletion of ITM-0007 across waves."
    )
