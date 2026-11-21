import re
import math
from datetime import datetime
from flask import render_template, request, session, redirect, url_for, flash, jsonify
from config import get_db_connection
from utils.permissions import require_permission


def get_pagination_range(current_page, total_pages):
    """Generates sliding window pagination list with ellipsis for large page counts."""
    if total_pages <= 7:
        return list(range(1, total_pages + 1))
    
    pages = []
    if current_page <= 4:
        pages.extend(range(1, 6))
        pages.append('...')
        pages.append(total_pages)
    elif current_page >= total_pages - 3:
        pages.append(1)
        pages.append('...')
        pages.extend(range(total_pages - 4, total_pages + 1))
    else:
        pages.append(1)
        pages.append('...')
        pages.extend(range(current_page - 1, current_page + 2))
        pages.append('...')
        pages.append(total_pages)
    return pages


from utils.recommendation_parser import parse_call_badge


def query_research_data(cursor, filters):
    """
    Core query engine for fetching filtered, paginated research recommendations.
    """
    # Distinct segments
    cursor.execute("""
        SELECT DISTINCT segment 
        FROM recommendation 
        WHERE segment IS NOT NULL AND TRIM(segment) != '' 
        ORDER BY segment ASC
    """)
    seg_rows = cursor.fetchall() or []
    segments = [r["segment"] for r in seg_rows]

    date_preset = str(filters.get("date_preset") or "today").strip()
    selected_segment = str(filters.get("segment") or "all").strip()
    search_query = str(filters.get("search") or "").strip()
    start_date = str(filters.get("start_date") or "").strip()
    end_date = str(filters.get("end_date") or "").strip()
    date_range = str(filters.get("date_range") or "").strip()

    if date_preset == "custom" and date_range:
        if " to " in date_range:
            parts = date_range.split(" to ")
            start_date = parts[0].strip()
            end_date = parts[1].strip()
        else:
            start_date = date_range.strip()
            end_date = date_range.strip()

    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date

    try:
        page = int(filters.get("page", 1))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(filters.get("per_page", 10))
        if per_page not in [10, 15, 25, 50, 100]:
            per_page = 10
    except (ValueError, TypeError):
        per_page = 10

    where_clause = " WHERE 1=1"
    params = []

    if date_preset == "today":
        where_clause += " AND DATE(recommendation_time) = CURRENT_DATE()"
    elif date_preset == "yesterday":
        where_clause += " AND DATE(recommendation_time) = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)"
    elif date_preset == "this_week":
        where_clause += " AND YEARWEEK(recommendation_time, 1) = YEARWEEK(CURRENT_DATE(), 1)"
    elif date_preset == "this_month":
        where_clause += " AND YEAR(recommendation_time) = YEAR(CURRENT_DATE()) AND MONTH(recommendation_time) = MONTH(CURRENT_DATE())"
    elif date_preset == "custom":
        if start_date and end_date:
            where_clause += " AND DATE(recommendation_time) BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        elif start_date:
            where_clause += " AND DATE(recommendation_time) >= %s"
            params.append(start_date)

    if selected_segment and selected_segment != "all":
        where_clause += " AND segment = %s"
        params.append(selected_segment)

    if search_query:
        where_clause += " AND (recommendation LIKE %s OR segment LIKE %s)"
        search_like = f"%{search_query}%"
        params.extend([search_like, search_like])

    count_sql = "SELECT COUNT(*) as total FROM recommendation" + where_clause
    cursor.execute(count_sql, params)
    count_row = cursor.fetchone()
    total_count = count_row["total"] if count_row else 0
    total_pages = max(1, math.ceil(total_count / per_page))

    if page > total_pages:
        page = total_pages
    offset = max(0, (page - 1) * per_page)

    sql = """
        SELECT 
            id,
            parent_id,
            segment,
            recommendation,
            recommendation_time,
            flag,
            rational_done
        FROM recommendation
    """ + where_clause + " ORDER BY recommendation_time DESC, id DESC LIMIT %s OFFSET %s"

    exec_params = list(params) + [per_page, offset]
    cursor.execute(sql, exec_params)
    rows = cursor.fetchall() or []

    recommendations = []
    for r in rows:
        rec_time = r.get("recommendation_time")
        if isinstance(rec_time, datetime):
            time_fmt = rec_time.strftime("%d %b %Y, %I:%M %p")
            date_only = rec_time.strftime("%d %b %Y")
            clock_only = rec_time.strftime("%I:%M %p")
        elif rec_time:
            try:
                dt = datetime.strptime(str(rec_time)[:19], "%Y-%m-%d %H:%M:%S")
                time_fmt = dt.strftime("%d %b %Y, %I:%M %p")
                date_only = dt.strftime("%d %b %Y")
                clock_only = dt.strftime("%I:%M %p")
            except Exception:
                time_fmt = str(rec_time)
                date_only = str(rec_time)[:10]
                clock_only = str(rec_time)[11:16]
        else:
            time_fmt = "N/A"
            date_only = "N/A"
            clock_only = "N/A"

        call_info = parse_call_badge(r.get("recommendation", ""))
        is_update = (r.get("parent_id") and int(r["parent_id"]) > 0) or ("UPDATE" in str(r.get("recommendation", "")).upper())

        recommendations.append({
            "id": r["id"],
            "parent_id": r.get("parent_id") or 0,
            "segment": r.get("segment") or "RESEARCH",
            "recommendation": r.get("recommendation") or "",
            "time_fmt": time_fmt,
            "date_only": date_only,
            "clock_only": clock_only,
            "call_badge": call_info["badge"],
            "call_color": call_info["color"],
            "call_css_class": call_info.get("css_class", "bg-primary-subtle text-primary border border-primary-subtle fw-semibold fs-11 px-2 py-1"),
            "is_update": is_update
        })

    start_index = ((page - 1) * per_page) + 1 if total_count > 0 else 0
    end_index = min(page * per_page, total_count)
    page_numbers = get_pagination_range(page, total_pages)

    if start_date and end_date:
        formatted_date_range = f"{start_date} to {end_date}"
    elif start_date:
        formatted_date_range = start_date
    else:
        formatted_date_range = date_range

    return {
        "segments": segments,
        "recommendations": recommendations,
        "date_preset": date_preset,
        "selected_segment": selected_segment,
        "search_query": search_query,
        "start_date": start_date,
        "end_date": end_date,
        "date_range": formatted_date_range,
        "page": page,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "total_count": total_count,
        "total_pages": total_pages,
        "start_index": start_index,
        "end_index": end_index
    }


def research_routes(app):

    @app.route("/research", endpoint="research_home")
    def research_home():
        flash("The Research module has been removed.", "info")
        return redirect(url_for("dashboard"))

        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for("dashboard"))

        try:
            with conn.cursor() as cursor:
                data = query_research_data(cursor, request.args)
        except Exception as e:
            print("Error loading research page data:", e)
            data = {
                "segments": [],
                "recommendations": [],
                "date_preset": "today",
                "selected_segment": "all",
                "search_query": "",
                "start_date": "",
                "end_date": "",
                "date_range": "",
                "page": 1,
                "per_page": 10,
                "page_numbers": [1],
                "total_count": 0,
                "total_pages": 1,
                "start_index": 0,
                "end_index": 0
            }
        finally:
            conn.close()

        return render_template(
            "research/research_home.html",
            segments=data["segments"],
            recommendations=data["recommendations"],
            date_preset=data["date_preset"],
            selected_segment=data["selected_segment"],
            search_query=data["search_query"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            date_range=data["date_range"],
            page=data["page"],
            per_page=data["per_page"],
            page_numbers=data["page_numbers"],
            total_count=data["total_count"],
            total_pages=data["total_pages"],
            start_index=data["start_index"],
            end_index=data["end_index"],
            active_group="research",
            active_page="research_home",
            page_title="Research Recommendations",
            page_heading="Research Recommendations"
        )

    @app.route("/api/research/list", methods=["POST"], endpoint="api_research_list")
    @require_permission("research", "view")
    def api_research_list():
        """
        Asynchronous POST endpoint for pulling filtered and paginated research data.
        """
        payload = request.get_json() or {}
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection error"}), 500

        try:
            with conn.cursor() as cursor:
                data = query_research_data(cursor, payload)
                data["success"] = True
                return jsonify(data)
        except Exception as e:
            print("Error in api_research_list:", e)
            return jsonify({"success": False, "error": str(e)}), 500
    @app.route("/api/research/notifications", methods=["GET", "POST"], endpoint="api_research_notifications")
    @require_permission("research", "view")
    def api_research_notifications():
        """
        Dedicated endpoint for pulling today's research calls for the header notification dropdown.
        """
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "notifications": []}), 500

        notifications = []
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, segment, recommendation, recommendation_time
                    FROM recommendation
                    WHERE DATE(recommendation_time) = CURRENT_DATE()
                    ORDER BY recommendation_time DESC, id DESC
                    LIMIT 25
                """)
                rows = cursor.fetchall() or []
                if not rows:
                    cursor.execute("""
                        SELECT id, segment, recommendation, recommendation_time
                        FROM recommendation
                        ORDER BY recommendation_time DESC, id DESC
                        LIMIT 15
                    """)
                    rows = cursor.fetchall() or []

                for r in rows:
                    rec_time = r.get("recommendation_time")
                    if isinstance(rec_time, datetime):
                        time_str = rec_time.strftime("%I:%M %p, %d %b")
                    else:
                        time_str = str(rec_time)[:16] if rec_time else "Just now"
                    call_info = parse_call_badge(r.get("recommendation", ""))
                    notifications.append({
                        "id": r["id"],
                        "segment": r.get("segment") or "RESEARCH",
                        "recommendation": r.get("recommendation") or "",
                        "time_str": time_str,
                        "badge": call_info["badge"],
                        "css_class": call_info.get("css_class", "")
                    })
        except Exception as e:
            print("Error loading research notifications:", e)
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "count": len(notifications),
            "notifications": notifications
        })

    @app.route("/api/cron/sync-research", methods=["GET", "POST"], endpoint="api_cron_sync_research")
    def api_cron_sync_research():
        """Public endpoint to trigger research sync via Web URL cron, curl, or webhook."""
        from cron.sync_research import sync_research_recommendations
        res = sync_research_recommendations()
        return jsonify(res)




