import csv


def parse_csv(file_path: str) -> list[dict]:
    """
    Parse uploaded CSV, returning list of row dicts.
    Detects the email column automatically.
    Each row dict includes all original columns + normalised 'email' field.
    """
    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return rows

        # Find the email column (case-insensitive)
        email_field = None
        for field in reader.fieldnames:
            if 'email' in field.lower():
                email_field = field
                break

        if email_field is None:
            # Fallback: use first column
            email_field = reader.fieldnames[0]

        for row in reader:
            email = row.get(email_field, "").strip().lower()
            if email and "@" in email:
                row["email"] = email
                rows.append(row)

    return rows
