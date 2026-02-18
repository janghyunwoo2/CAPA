import time
import boto3
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class AthenaClient:
    def __init__(self, database, s3_staging_dir, region_name):
        self.database = database
        self.s3_staging_dir = s3_staging_dir
        self.athena_client = boto3.client("athena", region_name=region_name)

    def run_query(self, sql: str) -> pd.DataFrame:
        """Athena에서 SQL 실행 및 결과 반환"""
        logger.info(f"Executing Athena SQL: {sql}")

        response = self.athena_client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": self.database},
            ResultConfiguration={"OutputLocation": self.s3_staging_dir},
        )
        query_execution_id = response["QueryExecutionId"]

        max_attempts = 60
        attempts = 0
        while attempts < max_attempts:
            execution = self.athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            state = execution["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                break
            elif state in ["FAILED", "CANCELLED"]:
                reason = execution["QueryExecution"]["Status"].get(
                    "StateChangeReason", "Unknown"
                )
                raise Exception(f"Athena query {state}: {reason}")

            time.sleep(1)
            attempts += 1
        else:
            raise Exception("Athena query timed out")

        paginator = self.athena_client.get_paginator("get_query_results")
        results_iter = paginator.paginate(QueryExecutionId=query_execution_id)

        rows = []
        columns = []

        for results in results_iter:
            if not columns:
                columns = [
                    col["Name"]
                    for col in results["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
                ]

            for row in results["ResultSet"]["Rows"]:
                data = [val.get("VarCharValue", None) for val in row["Data"]]
                rows.append(data)

        if not rows:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(rows, columns=columns)
        if len(df) > 0 and list(df.iloc[0]) == columns:
            df = df.iloc[1:].reset_index(drop=True)

        return df
