from __future__ import annotations

import pytest

from adeptix import KNOWN_ERROR_CODES, AdeptixApiError, AdeptixClient
from conftest import FakeTransport

BODY = {
    "error": "email_unverified",
    "message": "Verify your email address in the dashboard before creating live payments. Test keys are not affected.",
}


def test_email_unverified_is_a_known_code_and_surfaces_on_both_create_calls():
    assert "email_unverified" in KNOWN_ERROR_CODES
    assert len(KNOWN_ERROR_CODES) == len(set(KNOWN_ERROR_CODES))
    transport = FakeTransport((403, BODY), (403, BODY))
    client = AdeptixClient("ak_live_test", transport=transport)
    with pytest.raises(AdeptixApiError) as info:
        client.crypto.create_payment_request(chain="bsc", token="USDT", amount="10.00")
    assert info.value.status == 403
    assert info.value.code == "email_unverified"
    with pytest.raises(AdeptixApiError) as info2:
        client.payments.create(amount="10.00", currency="USD", email="a@example.com", provider="stripe")
    assert info2.value.code == "email_unverified"
