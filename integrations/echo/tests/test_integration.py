import io
import json
import unittest
from contextlib import redirect_stdout

from databricks.lakeflow.integrations._runtime import _run_function
from lakeflow_echo.integration import echo


class EchoTest(unittest.TestCase):
    def test_prints_message_requested_number_of_times(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            result = echo("hello", 3)

        self.assertIsNone(result)
        self.assertEqual(output.getvalue().splitlines(), ["hello", "hello", "hello"])

    def test_prints_nothing_when_repeat_count_is_zero(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            echo("hello", 0)

        self.assertEqual(output.getvalue(), "")

    def test_rejects_negative_repeat_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "repeat_count must be non-negative"):
            echo("hello", -1)

    def test_runtime_resolves_main_and_converts_named_parameters(self) -> None:
        output = io.StringIO()
        context = {
            "main": "lakeflow_echo.integration.echo",
            "task_key": "echo",
            "job_run_id": 1,
            "task_run_id": 2,
            "job_id": 3,
        }

        with redirect_stdout(output):
            result = _run_function(
                bindings={"message": "from runtime", "repeat_count": "2"},
                ctx=context,
            )

        mime_bundle, metadata = result._repr_mimebundle_()
        payload = json.loads(mime_bundle["application/vnd.databricks.pythonoperatortask+json"])
        self.assertEqual(output.getvalue().splitlines(), ["from runtime", "from runtime"])
        self.assertEqual(payload, {"outcome": "COMPLETED"})
        self.assertEqual(metadata, {})


if __name__ == "__main__":
    unittest.main()
