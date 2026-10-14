import pytest

from dubguard.evaluation import load_dataset, request_for


@pytest.fixture
def dataset():
    return load_dataset()


@pytest.fixture
def case_request(dataset):
    profiles, cases, _ = dataset
    return lambda case_id: request_for(next(c for c in cases if c.id == case_id), profiles)
