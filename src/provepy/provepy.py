import inspect
import ast
from .generate import verify

import shutil
import os
from pathlib import Path

import hashlib
import pickle

from functools import wraps

import textwrap

import sqlite3

from .utils import get_project_root

log=bool(int(os.getenv("PROVEPY_LOG","1")))


def get_lake_path():
    """Finds the lake executable, even if PATH isn't updated yet."""
    # Check standard PATH first
    path = shutil.which("lake")
    if path:
        return path
    
    # Fallback to default elan install locations
    home = Path.home()
    if os.name == "nt":  # Windows
        fallback = home / ".elan" / "bin" / "lake.exe"
    else:  # macOS / Linux
        fallback = home / ".elan" / "bin" / "lake"
        
    if fallback.exists():
        return str(fallback)
    
    raise FileNotFoundError("Lean/Lake not found. Did you run 'init'?")


def get_hash(source):
    source_bytes = source.encode('utf-8')
    return hashlib.sha256(source_bytes).hexdigest()

def _init_db(db_path):
    """Ensure the database and table exist."""
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                claim TEXT,
                hash TEXT,
                PRIMARY KEY (claim, hash)
            )
        ''')

def in_cache(claim, source):
    root = get_project_root()
    db_file = root / '.provepy_cache.db'
    _init_db(db_file)
    
    hash_val = get_hash(source)
    
    with sqlite3.connect(db_file) as conn:
        cursor = conn.execute(
            "SELECT 1 FROM cache WHERE claim = ? AND hash = ?", 
            (claim, hash_val)
        )
        # fetchone() returns a row (or None), so we check if it exists
        return cursor.fetchone() is not None

def update_cache(claim, source):
    root = get_project_root()
    db_file = root / '.provepy_cache.db'
    _init_db(db_file)
    
    hash_val = get_hash(source)
    
    with sqlite3.connect(db_file) as conn:
        # INSERT OR IGNORE prevents errors if the entry already exists
        conn.execute(
            "INSERT OR IGNORE INTO cache (claim, hash) VALUES (?, ?)", 
            (claim, hash_val)
        )


class VerificationError(Exception):
    """Raised when lean 4 fails to formally verify the python function."""
    pass

def provable(claim: str, context=[]):
    
    def decorator(func):
        try:
            raw_source_code = inspect.getsource(func)
        except OSError:
            raise RuntimeError("@provable cannot be used in interactive shells or REPLs. Please run it from a saved .py file.")        
        
        raw_source_code = textwrap.dedent(raw_source_code)
        
        tree=ast.parse(raw_source_code)
        
        func_node=tree.body[0]
        
        func_node.decorator_list=[]
        
        source_without_decorators=ast.unparse(func_node)
        
        context_string=""
        for function in context:
            try:
                context_source_code = inspect.getsource(function)
            except OSError:
                raise RuntimeError("Functions passed as context should be written in python, not C")        
            context_string+=context_source_code
            context_string+="\n"

        source_without_decorators=str(source_without_decorators)
        source=context_string+source_without_decorators

        signature=inspect.signature(func)
        signature=f"def {func.__name__}{signature}:"
        if log:
            print("Proving ",str(func.__name__))
        if in_cache(claim,source):
            verified=True
        else:
            verified, error =verify(source,signature,claim,get_lake_path())

        if not verified:
            raise VerificationError(
                "\n"
                f"Verification failed for '{func.__name__}'\n"
            )
        else:
            update_cache(claim, source)
            if log:
                print("Proved")
        
        @wraps(func)
        def wrapper(*args,**kwargs):
            return func(*args,**kwargs)
        
        return wrapper
    
    return decorator
    
