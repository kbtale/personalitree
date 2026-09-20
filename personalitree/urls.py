"""
URL configuration for the project.

PersonaliTree has no HTTP surface: it is driven from the command line, and the
worker consumes the Django Q2 queue. This module exists because Django expects
ROOT_URLCONF to resolve to a module containing ``urlpatterns``.
"""

urlpatterns: list = []
