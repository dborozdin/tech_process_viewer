"""
Schema package for API request/response validation using Marshmallow.
"""

from .common_schemas import ErrorSchema, PaginationSchema, SuccessResponseSchema

__all__ = [
    'ErrorSchema',
    'PaginationSchema',
    'SuccessResponseSchema',
]
