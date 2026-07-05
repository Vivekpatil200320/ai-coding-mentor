from main import generate_report


def test_first_page_returns_full_page_size():
    result = generate_report(page=1, page_size=10)
    assert len(result["items"]) == 10


def test_second_page_contains_correct_id_range():
    result = generate_report(page=2, page_size=10)
    ids = [item["id"] for item in result["items"]]
    assert ids == list(range(11, 21))


def test_total_items_matches_dataset_size():
    result = generate_report(page=1, page_size=10)
    assert result["total_items"] == 25


def test_last_page_contains_remaining_items():
    result = generate_report(page=3, page_size=10)
    assert len(result["items"]) == 5


def test_all_items_appear_exactly_once_across_pages():
    seen_ids = []
    for page in (1, 2, 3):
        result = generate_report(page=page, page_size=10)
        seen_ids.extend(item["id"] for item in result["items"])
    assert sorted(seen_ids) == list(range(1, 26))


def test_min_score_filter_excludes_low_scores():
    result = generate_report(page=1, page_size=25, min_score=101)
    assert result["total_items"] == 0
