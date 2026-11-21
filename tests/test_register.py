from data.validate_register import check_record

OK = {
    "source_id": "s1",
    "url": "https://example.org",
    "retrieved_on": "2026-11-19",
    "publisher": "p",
    "licence": "n/a",
    "scope": "x",
    "verification_status": "unverified",
}


def test_ok():
    assert check_record(OK) == []


def test_bad():
    assert check_record(
        {**OK, "retrieved_on": "yesterday", "verification_status": "maybe"}
    )
    assert check_record({"url": "ftp://x"})
