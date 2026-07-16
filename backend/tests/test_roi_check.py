"""Pure-logic tests for the ROI check. No Vertex/BigQuery access or .env required.

Uses `FakeMemberRecordsClient` seeded with rows that mirror the real BigQuery
`humana_hackathon.roi_authorizations` data, so the assertions stay meaningful.
The self-check is identity-based (caller_id == subject_member_id), per plan note #5a.
"""
from datetime import date

import pytest

from src.agents.roi_gatekeeper import check_roi_authorization
from src.clients.member_records import Authorization, FakeMemberRecordsClient
from src.models import ROIStatus

TODAY = date(2026, 7, 16)

AUTHS = [
    # MBR00001: one valid sibling authorization.
    Authorization("A1", "MBR00001", "Daniel Barrett", "Sibling", True, "2027-06-23", False),
    # MBR00002: a valid parent auth AND an expired power-of-attorney auth.
    Authorization("A2", "MBR00002", "Marcus Williams", "Parent", True, "2026-12-15", False),
    Authorization("A3", "MBR00002", "Jennifer Saunders", "Power of Attorney", True, "2024-11-15", True),
    # MBR00003: a row exists but no authorization is on file (blank caller).
    Authorization("A4", "MBR00003", "", "", False, "", False),
]


@pytest.fixture
def client():
    return FakeMemberRecordsClient(AUTHS)


def test_verified(client):
    r = check_roi_authorization("MBR00001", "Daniel Barrett", client=client, today=TODAY)
    assert r.status == ROIStatus.VERIFIED
    assert r.reason == "authorized"
    assert r.relationship == "Sibling"


def test_not_required_when_caller_is_member(client):
    r = check_roi_authorization("MBR00001", "The Member", caller_id="MBR00001", client=client, today=TODAY)
    assert r.status == ROIStatus.NOT_REQUIRED
    assert r.reason == "self"


def test_missing_expired(client):
    r = check_roi_authorization("MBR00002", "Jennifer Saunders", client=client, today=TODAY)
    assert r.status == ROIStatus.EXPIRED
    assert r.reason == "expired"


def test_second_caller_valid_while_first_expired(client):
    r = check_roi_authorization("MBR00002", "Marcus Williams", client=client, today=TODAY)
    assert r.status == ROIStatus.VERIFIED


def test_missing_no_authorization_on_file(client):
    r = check_roi_authorization("MBR00003", "Anyone", client=client, today=TODAY)
    assert r.status == ROIStatus.MISSING
    assert r.reason == "no_authorization"


def test_unknown_member_when_no_records(client):
    r = check_roi_authorization("MBR99999", "Anyone", client=client, today=TODAY)
    assert r.status == ROIStatus.UNKNOWN
    assert r.reason == "unknown_member"


def test_caller_name_is_case_insensitive(client):
    r = check_roi_authorization("MBR00001", "daniel barrett", client=client, today=TODAY)
    assert r.status == ROIStatus.VERIFIED


def test_caller_id_mismatch_does_not_grant_self(client):
    # A different member id must NOT count as self.
    r = check_roi_authorization("MBR00001", "Someone", caller_id="MBR00002", client=client, today=TODAY)
    assert r.status != ROIStatus.NOT_REQUIRED
