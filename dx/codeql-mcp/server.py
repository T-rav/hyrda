#!/usr/bin/env python3
from fastmcp import FastMCP, Context
from codeqlclient import CodeQLQueryServer
from pathlib import Path

mcp = FastMCP("CodeQL")
qs = CodeQLQueryServer()
qs.start()


@mcp.tool()
async def register_database(db_path: str) -> str:
    """This tool registers a CodeQL database given a path"""
    db_path_resolved = Path(db_path).resolve()
    if not db_path_resolved.exists():
        return f"Database path does not exist: {db_path}"

    source_zip = db_path_resolved / "src.zip"
    if not source_zip.exists():
        return f"Missing required src.zip in: {db_path}"

    db_entry = {
        "uri": Path(db_path).resolve().as_uri(),
        "content": {
            "sourceArchiveZip": (Path(db_path) / "src.zip").resolve().as_uri(),
            "dbDir": Path(db_path).resolve().as_uri(),
        },
    }
    callback, done, result_holder = qs.wait_for_completion_callback()
    qs.register_databases(
        [db_path],
        callback=callback,
        progress_callback=lambda msg: print("[progress] register:", msg),
    )
    done.wait()
    return f"Database registered: {db_path}"


@mcp.tool()
async def quick_evaluate(
    file: str, db: str, symbol: str, output_path: str = "/tmp/quickeval.bqrs"
) -> str:
    """This will allow you to quick_evaluate either a class or a predicate in a codeql query"""
    try:
        start, scol, end, ecol = qs.find_class_identifier_position(file, symbol)
    except ValueError:
        start, scol, end, ecol = qs.find_predicate_identifier_position(
            file, symbol
        )
    try:
        qs.quick_evaluate_and_wait(
            file, db, output_path, start, scol, end, ecol
        )
    except RuntimeError as re:
        return f"CodeQL evaluation failed: {re}"
    return output_path


@mcp.tool()
async def decode_bqrs(bqrs_path: str, fmt: str) -> str:
    """This can be used to decode CodeQL results, format is either csv for problem queries or json for path-problems"""
    return qs.decode_bqrs(bqrs_path, fmt)


@mcp.tool()
async def evaluate_query(
    query_path: str, db_path: str, output_path: str = "/tmp/eval.bqrs"
) -> str:
    """Runs a CodeQL query on a given database"""
    try:
        qs.evaluate_and_wait(query_path, db_path, output_path)
    except RuntimeError as re:
        return f"CodeQL evaluation failed: {re}"
    return output_path


@mcp.tool()
async def find_class_position(file: str, name: str) -> dict:
    """Finds startline, startcol, endline endcol of a class for quickeval"""
    start, scol, end, ecol = qs.find_class_identifier_position(file, name)
    return {
        "start_line": start,
        "start_col": scol,
        "end_line": end,
        "end_col": ecol,
    }


@mcp.tool()
async def find_predicate_position(file: str, name: str) -> dict:
    """Finds startline, startcol, endline endcol of a predicate for quickeval"""
    start, scol, end, ecol = qs.find_predicate_identifier_position(file, name)
    return {
        "start_line": start,
        "start_col": scol,
        "end_line": end,
        "end_col": ecol,
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
