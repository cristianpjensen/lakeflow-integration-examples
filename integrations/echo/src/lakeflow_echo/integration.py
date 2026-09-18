from databricks.lakeflow.integrations import integration


@integration(display_name="Echo", description="Prints a message a specified number of times.")
def echo(message: str, repeat_count: int) -> None:
    if repeat_count < 0:
        raise ValueError("repeat_count must be non-negative")

    for _ in range(repeat_count):
        print(message)
