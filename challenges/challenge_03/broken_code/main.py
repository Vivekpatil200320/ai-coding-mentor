"""
Generates a paginated user activity report.

Pulls raw records, computes a display name and letter grade for each,
sorts them, formats them into report lines, and returns the requested
page. Everything lives in one function because it started small and
just kept growing.
"""

RAW_RECORDS = [
    {"id": i, "name": f"user-{i}", "score": (i * 37) % 101}
    for i in range(1, 26)
]


def generate_report(page: int = 1, page_size: int = 10, min_score: int = 0):
    # --- fetch ---
    # In a real system this would hit a database or an external service.
    # Here we just grab the in-memory dataset and make a defensive copy
    # so callers can't accidentally mutate the module-level list.
    records = []
    for r in RAW_RECORDS:
        records.append(dict(r))

    # --- filter ---
    # Only include records that meet the minimum score threshold. This
    # was bolted on later when someone wanted a "top performers" view.
    filtered = []
    for r in records:
        if r["score"] >= min_score:
            filtered.append(r)

    # --- transform ---
    # Compute a couple of derived fields for the report: a display name
    # and a letter grade bucket based on the raw numeric score.
    transformed = []
    for r in filtered:
        if r["score"] >= 80:
            grade = "A"
        elif r["score"] >= 50:
            grade = "B"
        else:
            grade = "C"

        transformed.append(
            {
                "id": r["id"],
                "display_name": r["name"].upper(),
                "score": r["score"],
                "grade": grade,
            }
        )

    # --- sort ---
    # Keep the report in a stable, predictable order regardless of
    # whatever order the "database" happened to return rows in.
    transformed.sort(key=lambda t: t["id"])

    # --- format ---
    # Build the human-readable line that actually gets displayed,
    # separately from the structured fields above.
    formatted = []
    for t in transformed:
        line = f"{t['display_name']} — {t['score']} ({t['grade']})"
        formatted.append({"id": t["id"], "line": line})

    # --- paginate ---
    # Slice out just the page the caller asked for. `page` is 1-indexed
    # to match what the frontend shows the user.
    start = (page - 1) * page_size
    end = start + page_size - 1
    page_items = formatted[start:end]

    total_items = len(formatted)
    total_pages = (total_items + page_size - 1) // page_size

    return {
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "items": page_items,
    }
