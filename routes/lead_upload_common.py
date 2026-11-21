import csv
import io
import re
import secrets
import zipfile
from datetime import datetime, timedelta
from xml.etree import ElementTree

from config import get_db_connection
from routes.settings_helpers import (
    clean_address,
    clean_email,
    clean_name,
    decrypt_mobile,
    encrypt_mobile,
    make_unique_code,
    validate_indian_mobile,
)

RAW_RETENTION_DAYS = 7

def normalize_mobile(value):
    return validate_indian_mobile(value)


def split_pasted_numbers(text):
    return [
        token.strip()
        for token in re.split(r"[\s,;]+", text or "")
        if token.strip()
    ]


def column_label(index):
    label = ""
    while index >= 0:
        label = chr(65 + (index % 26)) + label
        index = index // 26 - 1
    return label


def detect_csv_delimiter(content):
    lines = [line for line in content.splitlines() if line.strip()][:25]
    if not lines:
        return ","

    candidates = [",", ";", "\t", "|"]
    best_delimiter = ","
    best_score = 0
    for delimiter in candidates:
        counts = []
        for line in lines:
            try:
                parsed = next(csv.reader([line], delimiter=delimiter))
            except csv.Error:
                parsed = [line]
            if len(parsed) > 1:
                counts.append(len(parsed))
        if not counts:
            continue
        avg = sum(counts) / len(counts)
        variance = sum((c - avg) ** 2 for c in counts) / len(counts)
        score = (avg * 10) - variance
        if score > best_score:
            best_score = score
            best_delimiter = delimiter

    return best_delimiter


def read_csv_rows(file_storage, has_header=True):
    raw = file_storage.read()

    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1", errors="replace")

    delimiter = detect_csv_delimiter(content)
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)

    all_rows = []
    for row in reader:
        cleaned_row = [str(cell or "").strip() for cell in row]
        if any(cleaned_row):
            all_rows.append(cleaned_row)

    if not all_rows:
        return [], []

    if has_header:
        headers = [header if header else f"Column_{column_label(idx)}" for idx, header in enumerate(all_rows[0])]
        rows_data = all_rows[1:]
    else:
        headers = [f"Column_{column_label(idx)}" for idx in range(len(all_rows[0]))]
        rows_data = all_rows

    records = []
    for row in rows_data:
        record = {}
        for idx, header in enumerate(headers):
            record[header] = row[idx] if idx < len(row) else ""
        records.append(record)

    return records, headers


def get_existing_leads(cursor, normalized_numbers):
    if not normalized_numbers:
        return {}

    encrypted_by_normalized = {
        normalized: encrypt_mobile(normalized)
        for normalized in normalized_numbers
        if normalized
    }
    encrypted_numbers = [e for e in encrypted_by_normalized.values() if e]
    if not encrypted_numbers:
        return {}

    existing = {}
    chunk_size = 2000
    for i in range(0, len(encrypted_numbers), chunk_size):
        chunk = encrypted_numbers[i:i + chunk_size]
        placeholders = ", ".join(["%s"] * len(chunk))
        cursor.execute(f"""
            SELECT
                l.id,
                l.lead_uuid,
                l.mobile_number,
                l.lead_status,
                l.current_owner_user_id,
                l.lead_source,
                l.created_at,
                l.updated_at,
                u.full_name AS current_owner
            FROM leads l
            LEFT JOIN users u ON u.id = l.current_owner_user_id
            WHERE l.mobile_number IN ({placeholders})
        """, chunk)
        rows = cursor.fetchall() or []
        for row in rows:
            try:
                dec = decrypt_mobile(row["mobile_number"])
                if dec:
                    existing[dec] = row
                existing[row["mobile_number"]] = row
            except Exception:
                continue
    return existing


def _batch_item_payload(row, status, normalized_mobile=None, message="", existing_lead=None, row_number=0):
    encrypted_mobile = encrypt_mobile(normalized_mobile) if normalized_mobile else None
    if not encrypted_mobile:
        attempted, _message = normalize_mobile(row.get("mobile_number"))
        encrypted_mobile = encrypt_mobile(attempted) if attempted else None
    return {
        "row_number": row_number,
        "name": row.get("name") or "",
        "mobile_number": encrypted_mobile or row.get("mobile_number") or "",
        "email": row.get("email") or "",
        "address": row.get("address") or "",
        "item_status": status,
        "validation_message": message,
        "duplicate_lead_id": existing_lead.get("id") if existing_lead else None,
        "duplicate_lifecycle_status": existing_lead.get("lead_status") if existing_lead else None,
    }


def prepare_records_from_paste(text):
    return [
        {
            "row_number": index,
            "name": "",
            "mobile_number": token,
            "email": "",
            "address": "",
        }
        for index, token in enumerate(split_pasted_numbers(text), start=1)
    ]


def prepare_records_from_file(file_storage, mapping):
    rows, headers = read_csv_rows(file_storage, has_header=mapping.get("has_header", True))

    def resolve_col(val):
        """Form sends column index as string (e.g. '0', '2'). Convert to actual header name."""
        if not val and val != 0:
            return None
        val_str = str(val).strip()
        if val_str.isdigit():
            idx = int(val_str)
            return headers[idx] if idx < len(headers) else None
        # Already a header name
        return val_str if val_str in headers else None

    mobile_col = resolve_col(mapping.get("mobile_column"))
    if not mobile_col:
        # Auto-detect by keyword
        for h in headers:
            if any(kw in h.lower() for kw in ["mobile", "phone", "contact", "number", "cell"]):
                mobile_col = h
                break
    if not mobile_col and headers:
        mobile_col = headers[0]

    name_col    = resolve_col(mapping.get("name_column"))
    email_col   = resolve_col(mapping.get("email_column"))
    address_col = resolve_col(mapping.get("address_column"))

    records = []
    for index, row in enumerate(rows, start=1):
        records.append({
            "row_number":    index,
            "name":          clean_name(row.get(name_col, "")) if name_col else "",
            "mobile_number": row.get(mobile_col, "").strip() if mobile_col else "",
            "email":         clean_email(row.get(email_col, "")) if email_col else "",
            "address":       clean_address(row.get(address_col, "")) if address_col else "",
        })
    return records


def create_lead_batch(conn, upload_type, batch_name, records, uploaded_by, lead_source=None):
    with conn.cursor() as cursor:
        resolved_source_id = resolve_lead_source_id(cursor, lead_source) if lead_source else None
        normalized_candidates = []
        prepared = []
        for record in records:
            normalized_mobile, message = normalize_mobile(record.get("mobile_number"))
            prepared.append((record, normalized_mobile, message))
            if normalized_mobile:
                normalized_candidates.append(normalized_mobile)

        existing_leads = get_existing_leads(cursor, sorted(set(normalized_candidates)))
        seen_fresh = set()
        items = []

        for record, normalized_mobile, message in prepared:
            if not normalized_mobile:
                items.append(_batch_item_payload(
                    record,
                    "invalid",
                    message=message,
                    row_number=record.get("row_number", 0),
                ))
                continue

            existing_lead = existing_leads.get(normalized_mobile)
            if existing_lead:
                items.append(_batch_item_payload(
                    record,
                    "duplicate",
                    normalized_mobile=normalized_mobile,
                    message="Duplicate lead already exists.",
                    existing_lead=existing_lead,
                    row_number=record.get("row_number", 0),
                ))
                continue

            if normalized_mobile in seen_fresh:
                items.append(_batch_item_payload(
                    record,
                    "duplicate",
                    normalized_mobile=normalized_mobile,
                    message="Duplicate within uploaded batch.",
                    row_number=record.get("row_number", 0),
                ))
                continue

            seen_fresh.add(normalized_mobile)
            items.append(_batch_item_payload(
                record,
                "fresh",
                normalized_mobile=normalized_mobile,
                row_number=record.get("row_number", 0),
            ))

        batch_uuid = f"LB{secrets.token_hex(6).upper()}"
        default_batch_name = datetime.now().strftime("Lead Batch - %d %b %Y %I:%M %p")
        cursor.execute("""
            INSERT INTO lead_batches (
                batch_uuid, batch_name, upload_type, lead_source, uploaded_by
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            batch_uuid,
            batch_name.strip() if batch_name and batch_name.strip() else default_batch_name,
            upload_type,
            resolved_source_id,
            uploaded_by,
        ))
        batch_id = cursor.lastrowid

        insert_items_sql = """
            INSERT INTO lead_batch_items (
                item_uuid, batch_id, `row_number`, name, mobile_number,
                email, address, item_status, validation_message,
                duplicate_lead_id, duplicate_lifecycle_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        batch_params = []
        for item in items:
            item_uuid = f"LBI{secrets.token_hex(8).upper()}"
            batch_params.append((
                item_uuid,
                batch_id,
                item["row_number"],
                item["name"],
                item["mobile_number"],
                item["email"],
                item["address"],
                item["item_status"],
                item["validation_message"],
                item["duplicate_lead_id"],
                item["duplicate_lifecycle_status"],
            ))

        chunk_size = 5000
        for i in range(0, len(batch_params), chunk_size):
            cursor.executemany(insert_items_sql, batch_params[i:i + chunk_size])

    conn.commit()
    return batch_uuid


def get_batch(cursor, batch_uuid):
    cursor.execute("""
        SELECT
            b.id AS legacy_id,
            b.id,
            b.batch_uuid,
            b.batch_name,
            b.upload_type,
            b.lead_source,
            COALESCE(ls.source_name, 'No Source') AS source_name,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id), 0) AS total_count,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id AND i.item_status != 'invalid'), 0) AS valid_count,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id AND i.item_status = 'invalid'), 0) AS invalid_count,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id AND i.item_status = 'fresh'), 0) AS fresh_count,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id AND i.item_status = 'duplicate'), 0) AS duplicate_count,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id AND i.item_status = 'imported'), 0) AS imported_count,
            b.uploaded_by,
            b.imported_at,
            b.created_at,
            b.updated_at,
            COALESCE(u.full_name, 'System') AS uploaded_by_name
        FROM lead_batches b
        LEFT JOIN users u ON u.user_uuid = b.uploaded_by
        LEFT JOIN lead_sources ls ON ls.id = b.lead_source
        WHERE b.batch_uuid = %s
        LIMIT 1
    """, (batch_uuid,))
    return cursor.fetchone()


def resolve_lead_source_id(cursor, lead_source_input):
    """
    Resolves lead_source_input (integer ID or string name) to valid integer ID from lead_sources table.
    Always returns integer e.g. 4, 2.
    """
    if not lead_source_input:
        return 1

    val = str(lead_source_input).strip()
    if val.isdigit():
        return int(val)

    cursor.execute("SELECT id FROM lead_sources WHERE source_name = %s LIMIT 1", (val,))
    row = cursor.fetchone()
    if row:
        return int(row["id"])

    cursor.execute("SELECT id FROM lead_sources WHERE source_uuid = %s LIMIT 1", (val,))
    row = cursor.fetchone()
    if row:
        return int(row["id"])

    return 1


def resolve_lead_status_id(cursor, lead_status_input):
    """
    Resolves lead_status_input to integer ID from lead_statuses table.
    """
    if lead_status_input:
        val = str(lead_status_input).strip()
        if val.isdigit():
            return int(val)
        
        cursor.execute("SELECT id FROM lead_statuses WHERE status_uuid = %s LIMIT 1", (val,))
        row = cursor.fetchone()
        if row:
            return int(row["id"])
        
        cursor.execute("SELECT id FROM lead_statuses WHERE status_name = %s AND status = 1 LIMIT 1", (val,))
        row = cursor.fetchone()
        if row:
            return int(row["id"])

    return None


def import_fresh_leads(
    conn,
    batch_uuid,
    lead_source,
    assign_to_user_uuid,
    imported_by_uuid,
    lead_status=None,
):
    with conn.cursor() as cursor:
        batch = get_batch(cursor, batch_uuid)
        if not batch:
            raise ValueError("Batch not found.")

        # Resolve imported_by user ID
        cursor.execute("SELECT id FROM users WHERE user_uuid = %s OR id = %s LIMIT 1", (imported_by_uuid, imported_by_uuid))
        u_row = cursor.fetchone()
        user_id = u_row["id"] if u_row else 1

        # Resolve assigned owner user ID (only if explicitly selected in form)
        owner_id = None
        if assign_to_user_uuid:
            val_u = str(assign_to_user_uuid).strip()
            cursor.execute(
                "SELECT id FROM users WHERE (user_uuid = %s OR id = %s) AND status = 1 LIMIT 1",
                (val_u, int(val_u) if val_u.isdigit() else 0)
            )
            o_row = cursor.fetchone()
            if o_row:
                owner_id = o_row["id"]

        cursor.execute("""
            SELECT id, name, mobile_number, email, address, `row_number`
            FROM lead_batch_items
            WHERE batch_id = %s AND item_status = 'fresh'
            ORDER BY `row_number` ASC
        """, (batch["id"],))
        fresh_items = cursor.fetchall() or []

        # Resolve lead_source and lead_status to integer IDs
        resolved_source_id = resolve_lead_source_id(cursor, lead_source)
        resolved_status_id = resolve_lead_status_id(cursor, lead_status)

        # Check existing leads in bulk
        fresh_mobiles = [decrypt_mobile(item["mobile_number"]) for item in fresh_items]
        existing = get_existing_leads(cursor, [m for m in fresh_mobiles if m])

        lead_params = []
        imported_item_ids = []
        dup_updates = []

        for item in fresh_items:
            normalized_mobile = decrypt_mobile(item["mobile_number"])
            if normalized_mobile in existing:
                existing_lead = existing[normalized_mobile]
                dup_updates.append((existing_lead["id"], existing_lead.get("lead_status"), item["id"]))
                continue

            lead_uuid = f"LEAD{secrets.token_hex(8).upper()}"
            lead_params.append((
                lead_uuid,
                batch["id"],
                item["name"] or None,
                item["mobile_number"],
                item["email"] or None,
                item["address"] or None,
                resolved_source_id,
                resolved_status_id,
                owner_id,
                user_id,
            ))
            imported_item_ids.append(item["id"])

        if dup_updates:
            cursor.executemany("""
                UPDATE lead_batch_items
                SET item_status = 'duplicate',
                    duplicate_lead_id = %s,
                    duplicate_lifecycle_status = %s,
                    validation_message = 'Duplicate found before import.'
                WHERE id = %s
            """, dup_updates)

        if lead_params:
            insert_leads_sql = """
                INSERT INTO leads (
                    lead_uuid, lead_batch_id, name, mobile_number,
                    email, address, lead_source, lead_status,
                    current_owner_user_id, created_by, comment, is_disposed, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '', 0, NOW(), NOW())
            """
            chunk_size = 5000
            for i in range(0, len(lead_params), chunk_size):
                cursor.executemany(insert_leads_sql, lead_params[i:i + chunk_size])

            for i in range(0, len(imported_item_ids), chunk_size):
                chunk_ids = imported_item_ids[i:i + chunk_size]
                ph = ", ".join(["%s"] * len(chunk_ids))
                cursor.execute(f"UPDATE lead_batch_items SET item_status = 'imported' WHERE id IN ({ph})", chunk_ids)

        imported_count = len(lead_params)
        cursor.execute("""
            UPDATE lead_batches
            SET imported_at = COALESCE(imported_at, NOW()),
                lead_source = COALESCE(lead_source, %s)
            WHERE id = %s
        """, (resolved_source_id, batch["id"]))

    conn.commit()
    return imported_count


def create_and_import_lead_batch(
    conn,
    upload_type,
    batch_name,
    records,
    uploaded_by,
    lead_source=None,
    lead_status=None,
    assign_to_user_uuid=None,
):
    batch_uuid = create_lead_batch(conn, upload_type, batch_name, records, uploaded_by, lead_source=lead_source)
    imported_count = import_fresh_leads(
        conn,
        batch_uuid,
        lead_source,
        assign_to_user_uuid,
        uploaded_by,
        lead_status=lead_status,
    )
    with conn.cursor() as cursor:
        batch = get_batch(cursor, batch_uuid)
    return batch_uuid, imported_count, batch


def get_batch_list_rows(cursor, limit=None):
    from_clause = f"(SELECT * FROM lead_batches ORDER BY id DESC LIMIT {int(limit)}) b" if limit else "lead_batches b"
    sql = f"""
        SELECT
            b.id,
            b.batch_uuid,
            b.batch_name,
            b.upload_type,
            b.lead_source,
            CASE 
                WHEN ls.source_name IS NOT NULL THEN ls.source_name
                WHEN (b.lead_source IS NOT NULL AND b.lead_source != '' AND b.lead_source != '0') THEN b.lead_source
                ELSE 'No Source'
            END AS source_name,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id), 0) AS total_count,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id AND i.item_status = 'imported'), 0) AS fresh_count,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id AND i.item_status = 'imported'), 0) AS imported_count,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id AND i.item_status = 'duplicate'), 0) AS duplicate_count,
            COALESCE((SELECT COUNT(*) FROM lead_batch_items i WHERE i.batch_id = b.id AND i.item_status = 'invalid'), 0) AS invalid_count,
            b.created_at,
            COALESCE(u.full_name, 'System') AS uploaded_by_name
        FROM {from_clause}
        LEFT JOIN users u ON u.user_uuid = b.uploaded_by
        LEFT JOIN lead_sources ls ON (ls.id = b.lead_source OR ls.source_uuid = b.lead_source OR ls.source_name = b.lead_source)
        ORDER BY b.id DESC
    """
    cursor.execute(sql)
    return cursor.fetchall()


def raw_data_available(batch):
    return True


def cleanup_expired_lead_batch_raw_data(cursor):
    pass


def serialize_value(value):
    if isinstance(value, (datetime,)):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def serialize_grid_rows(rows):
    return [
        {key: serialize_value(value) for key, value in row.items()}
        for row in (rows or [])
    ]


def csv_response(filename, fieldnames, rows):
    from flask import Response
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def get_batch_performance(cursor, batch=None, batch_uuid=None):
    return {
        "total_uploaded": 0,
        "fresh_imported": 0,
        "duplicate": 0,
        "invalid": 0,
    }


def get_performance_metrics(cursor, batch_uuid=None):
    return []


def get_duplicate_rows(cursor, batch_uuid):
    return []


def get_invalid_rows(cursor, batch_uuid):
    return []


def get_metric_rows(cursor, batch_uuid, metric):
    return []
