#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, time, importlib, inspect
from pathlib import Path
from typing import Dict, Any

def call(runner, blob: Path, workdir: Path, window_size: int, min_match: int)->Dict[str,Any]:
    mod_name, func_name = runner.split(":",1)
    mod = __import__(mod_name, fromlist=[func_name]); fn = getattr(mod, func_name)
    return fn(workdir=workdir, blob=blob, window_size=window_size, min_match=min_match)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blob", type=Path, required=True)
    ap.add_argument("--runner", default="tests.test_encoding:run_encoding_demo")
    args = ap.parse_args()
    res = call(args.runner, args.blob, Path(".pvrt"), 65536, 8)
    print(res)
if __name__=="__main__": main()
