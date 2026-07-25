def include_only_v1_endpoints(endpoints):
    """Keep legacy routes working without including them in Release 1 docs."""

    return [
        endpoint
        for endpoint in endpoints
        if endpoint[0].startswith("/api/v1/")
    ]
