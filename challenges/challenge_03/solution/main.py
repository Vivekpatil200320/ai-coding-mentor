"""
Generates a paginated user activity report.

Split into focused steps — fetch, filter, transform, sort, format,
paginate — so each one is independently readable and testable.
"""

RAW_RECORDS = [
    {"id": i, "name": f"user-{i}", "score": (i * 37) % 101}
    for i in range(1, 26)
]


def fetch_records():
    """Return a defensive copy of the raw dataset."""
    return [dict(r) for r in RAW_RECORDS]


def filter_by_min_score(records, min_score):
    return [r for r in records if r["score"] >= min_score]


def grade_for_score(score):
    if score >= 80:
        return "A"
    if score >= 50:
        return "B"
    return "C"


def transform_records(records):
    return [
        {
            "id": r["id"],
            "display_name": r["name"].upper(),
            "score": r["score"],
            "grade": grade_for_score(r["score"]),
        }
        for r in records
    ]


def format_records(records):
    sorted_records = sorted(records, key=lambda t: t["id"])
    return [
        {
            "id": t["id"],
            "line": f"{t['display_name']} — {t['score']} ({t['grade']})",
        }
        for t in sorted_records
    ]


def paginate(items, page, page_size):
    """1-indexed pagination: page 1 is the first `page_size` items."""
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]


def generate_report(page: int = 1, page_size: int = 10, min_score: int = 0):
    records = fetch_records()
    filtered = filter_by_min_score(records, min_score)
    transformed = transform_records(filtered)
    formatted = format_records(transformed)
    page_items = paginate(formatted, page, page_size)

    total_items = len(formatted)
    total_pages = (total_items + page_size - 1) // page_size

    return {
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "items": page_items,
    }
