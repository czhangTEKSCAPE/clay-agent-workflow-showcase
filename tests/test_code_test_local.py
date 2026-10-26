import json
import os
import tempfile
import unittest

from tests import _path  # noqa: F401
import code_test_local

NODE = '''
def handler(context):
    name = context.get_input("name")
    return {"greeting": "hi " + name, "count": 2}
'''


class RunTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.code = os.path.join(self.dir.name, "node.py")
        self.schema = os.path.join(self.dir.name, "out.json")
        with open(self.code, "w") as f:
            f.write(NODE)

    def tearDown(self):
        self.dir.cleanup()

    def write_schema(self, schema):
        with open(self.schema, "w") as f:
            json.dump(schema, f)

    def test_valid_output(self):
        self.write_schema({"greeting": {"type": "string"}, "count": {"type": "number"}})
        out, errs, extra = code_test_local.run(self.code, self.schema, {"name": "Ada"})
        self.assertEqual(out["greeting"], "hi Ada")
        self.assertEqual((errs, extra), ([], []))

    def test_reports_missing_and_wrong_type_and_extra(self):
        self.write_schema({"greeting": {"type": "number"}, "absent": {"type": "string"}})
        _, errs, extra = code_test_local.run(self.code, self.schema, {"name": "Ada"})
        self.assertEqual(len(errs), 2)
        self.assertEqual(extra, ["count"])

    def test_missing_input_raises_like_the_sandbox(self):
        self.write_schema({})
        with self.assertRaises(KeyError):
            code_test_local.run(self.code, self.schema, {})


if __name__ == "__main__":
    unittest.main()
