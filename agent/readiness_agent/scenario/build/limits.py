from google.cloud import bigquery

MAX_BYTES_BILLED = 100_000_000


def job_config(*params: bigquery.ScalarQueryParameter) -> bigquery.QueryJobConfig:
    return bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED, query_parameters=list(params)
    )
