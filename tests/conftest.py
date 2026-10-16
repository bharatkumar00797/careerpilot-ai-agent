"""Shared fixtures for CareerPilot tests."""

from __future__ import annotations

import pytest

from careerpilot.ingest import load_job, load_profile
from careerpilot.models import JobPosting, Profile


@pytest.fixture
def ml_profile() -> Profile:
    return load_profile("ml-engineer")


@pytest.fixture
def hybrid_profile() -> Profile:
    return load_profile("fullstack-pm-hybrid")


@pytest.fixture
def senior_backend() -> JobPosting:
    return load_job("senior-backend")


@pytest.fixture
def ml_platform() -> JobPosting:
    return load_job("ml-platform")


@pytest.fixture
def product_engineer() -> JobPosting:
    return load_job("product-engineer")
