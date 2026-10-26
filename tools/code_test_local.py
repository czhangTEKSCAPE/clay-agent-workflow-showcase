#!/usr/bin/env python3
"""Run a workflow code node locally the way Clay's sandbox would (context.get_input raises on a missing
input; every outputSchema field must be present, non-null and of the declared type).

Usage: code_test_local.py <code.py> <outputs.json> <inputs.json|-> [--show]
Use when `clay workflows code test` has hit its 10/day cap. Stdlib only, like the sandbox.
"""
import importlib.util, json, sys

TYPES = {"string": str, "number": (int, float), "boolean": bool, "array": list, "object": dict}


class Ctx:
    def __init__(self, d):
        self.d = d

    def get_input(self, k):
        if k not in self.d:
            raise KeyError(k)
        return self.d[k]


def run(code_path, out_path, inputs):
    spec = importlib.util.spec_from_file_location("node", code_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    out = mod.handler(Ctx(inputs))
    schema = json.load(open(out_path))
    errs = []
    for k, v in schema.items():
        if k not in out or out[k] is None:
            errs.append(f"missing {k}")
        elif not isinstance(out[k], TYPES[v["type"]]) or (v["type"] == "number" and isinstance(out[k], bool)):
            errs.append(f"{k}: {type(out[k]).__name__} != {v['type']}")
    extra = [k for k in out if k not in schema]
    return out, errs, extra


if __name__ == "__main__":
    code, outs, inp = sys.argv[1:4]
    inputs = json.load(sys.stdin if inp == "-" else open(inp))
    out, errs, extra = run(code, outs, inputs)
    print(json.dumps({"errors": errs, "extra_outputs": extra, "output": out if "--show" in sys.argv else {k: out[k] for k in list(out)[:12]}}, indent=1))
    sys.exit(1 if errs else 0)
