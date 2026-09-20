import io
import unittest
from contextlib import redirect_stdout

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


if __name__ == "__main__":
    unittest.main()
