"""Abstract syntax tree node definitions for PayScript."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    """Base class for syntax tree nodes."""

    line: int
    column: int
