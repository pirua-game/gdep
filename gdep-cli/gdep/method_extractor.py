"""
gdep/method_extractor.py

공유 메서드 본문 추출 유틸리티.
explain_method_logic, read_class_source, find_method_callers 등에서 공통으로 사용.
"""
from __future__ import annotations

import re


def extract_brace_body(text: str, brace_start: int) -> str | None:
    """{ ... } 블록 본문 추출. 중첩 중괄호 처리."""
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start + 1:i]
    return None


def extract_cpp_method(source: str, method_name: str) -> tuple[str, int] | None:
    """C++/UE5 메서드 본문 추출.
    Returns (body_text, match_start_position) or None."""
    try:
        from gdep.cpp_flow import _extract_function_body
        result = _extract_function_body(source, method_name)
        if result is not None:
            return (result, 0)
    except Exception:
        pass

    # Fallback 1: ClassName::method_name 패턴
    pat = re.compile(
        r'\b\w+\s*::\s*' + re.escape(method_name) + r'\s*\([^{;]*\)\s*(?:const\s*)?\{',
        re.DOTALL,
    )
    m = pat.search(source)
    if not m:
        # Fallback 2: namespace 스타일 (ClassName:: 없이 정의)
        pat_ns = re.compile(
            r'(?:^|\n)[ \t]*(?:[\w:<>*& ]+[ \t]+)' + re.escape(method_name) + r'\s*\([^;{}]*\)\s*(?:const\s*)?\s*\{',
        )
        m = pat_ns.search(source)
    if not m:
        return None
    start = source.index("{", m.start())
    body = extract_brace_body(source, start)
    return (body, m.start()) if body else None


def extract_cs_method(source: str, method_name: str) -> tuple[str, int] | None:
    """C# 메서드 본문 추출.
    Returns (body_text, match_start_position) or None."""
    pat = re.compile(
        r'(?:(?:public|private|protected|internal|static|virtual|override|async|sealed|abstract|new)\s+)*'
        r'[\w<>\[\],\s]+\s+' + re.escape(method_name) + r'\s*\([^)]*\)\s*(?:\w+[^{]*?)?\{',
        re.DOTALL,
    )
    m = pat.search(source)
    if not m:
        # 단순 fallback
        pat2 = re.compile(r'\b' + re.escape(method_name) + r'\s*\([^)]*\)\s*\{', re.DOTALL)
        m = pat2.search(source)
        if not m:
            return None
    start = source.index("{", m.start())
    body = extract_brace_body(source, start)
    return (body, m.start()) if body else None


def extract_method_body(source: str, method_name: str, is_cpp: bool) -> tuple[str, int] | None:
    """엔진 타입에 따라 적절한 메서드 추출 함수를 호출.
    Returns (body_text, match_start_position) or None."""
    if is_cpp:
        return extract_cpp_method(source, method_name)
    return extract_cs_method(source, method_name)
