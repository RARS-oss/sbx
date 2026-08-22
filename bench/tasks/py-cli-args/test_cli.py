import unittest

from cli import parse_args


class TestParseArgs(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(parse_args([]), ({}, []))

    def test_positionals_only(self):
        self.assertEqual(parse_args(["a", "b"]), ({}, ["a", "b"]))

    def test_long_with_value(self):
        self.assertEqual(parse_args(["--name", "bob"]), ({"name": "bob"}, []))

    def test_long_equals_form(self):
        self.assertEqual(parse_args(["--name=bob"]), ({"name": "bob"}, []))

    def test_equals_with_empty_value(self):
        self.assertEqual(parse_args(["--name="]), ({"name": ""}, []))

    def test_equals_value_containing_equals(self):
        self.assertEqual(parse_args(["--expr=a=b"]), ({"expr": "a=b"}, []))

    def test_bare_flag_at_end(self):
        self.assertEqual(parse_args(["--verbose"]), ({"verbose": True}, []))

    def test_bare_flag_before_flag(self):
        self.assertEqual(parse_args(["--verbose", "--name", "x"]), ({"verbose": True, "name": "x"}, []))

    def test_repeated_last_wins(self):
        self.assertEqual(parse_args(["--name", "a", "--name", "b"]), ({"name": "b"}, []))

    def test_short_flag(self):
        self.assertEqual(parse_args(["-v"]), ({"v": True}, []))

    def test_short_with_value(self):
        self.assertEqual(parse_args(["-o", "out.txt", "in.txt"]), ({"o": "out.txt"}, ["in.txt"]))

    def test_double_dash_terminator(self):
        self.assertEqual(parse_args(["--name", "x", "--", "--not-a-flag", "-y"]), ({"name": "x"}, ["--not-a-flag", "-y"]))

    def test_double_dash_alone(self):
        self.assertEqual(parse_args(["--"]), ({}, []))

    def test_negative_number_is_positional_after_terminator(self):
        self.assertEqual(parse_args(["--", "-5"]), ({}, ["-5"]))

    def test_mixed(self):
        self.assertEqual(
            parse_args(["run", "--jobs=4", "-q", "--out", "dir", "file1", "--", "--weird"]),
            ({"jobs": "4", "q": True, "out": "dir"}, ["run", "file1", "--weird"]),
        )


if __name__ == "__main__":
    unittest.main()
