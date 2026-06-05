"""
Framework-Agnostic Gateway Layer (Area 2).

This package normalizes ANY test framework (Google Test, Unity, CppUTest,
PyTest, VectorCAST, Tessy, ASCET-SE, Custom BOSCH, and *future* frameworks)
into a single Common Internal Representation (CIR) so that every downstream
AI engine works on one unified data model — achieving "Zero LLM Framework
Learning".

Public surface:
    from adapters import AdapterRegistry, BaseAdapter, CIRTestCase, CIRSuite
"""

from adapters.cir import (
    AssertionType,
    CIRAssertion,
    CIRInput,
    CIRTestCase,
    CIRSuite,
    CIRMutant,
)
from adapters.base_adapter import BaseAdapter, AdapterCapabilities, ExecutionResult
from adapters.registry import AdapterRegistry, get_registry

__all__ = [
    "AssertionType",
    "CIRAssertion",
    "CIRInput",
    "CIRTestCase",
    "CIRSuite",
    "CIRMutant",
    "BaseAdapter",
    "AdapterCapabilities",
    "ExecutionResult",
    "AdapterRegistry",
    "get_registry",
]
