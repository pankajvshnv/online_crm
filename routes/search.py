"""
routes/search.py
================
Global CRM Search across Leads and Clients.
Classification Rules:
1. Converted / Paid Clients (has approved sales order or client record) -> Shown ONLY in Clients Table.
2. Active / Unconverted Leads -> Shown in Leads Table.
3. Exact matching for numeric IDs, mobile numbers, emails, UUIDs, and names.
4. Permission-aware data protection for unauthorized/unassigned records.
"""

from datetime import datetime
from flask import render_template, request, session, redirect, url_for, flash
from config import get_db_connection
from utils.permissions import has_permission
from routes.settings_helpers import (
    fetch_user_tree,
    fetch_logged_user_settings,
    fetch_last_dialed_lead_uuid,
    mask_mobile_number,
    decrypt_mobile,
    format_mobile_display
)
from routes.lead.all_leads_rows import prepare_lead_row


def search_routes(app):

    @app.route("/search", methods=["GET"], endpoint="global_search_page")
    def global_search_page():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        search_query = request.args.get("q", "").strip()
        leads_list = []
        clients_list = []
        total_leads = 0
        total_clients = 0
        total_results = 0

        if not search_query:
            return render_template(
                "search/global_search.html",
                search_query="",
                leads=[],
                clients=[],
                total_leads=0,
                total_clients=0,
                total_results=0,
                active_group="search",
                active_page="global_search",
                page_title="Global Search",
                page_heading="Search Results"
            )

        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for("dashboard"))

        try:
            with conn.cursor() as cursor:
                user_info = session.get("user") or {}
                user_id = user_info.get("id")
                is_admin = bool(user_info.get("is_admin")) or str(user_info.get("role_name", "")).lower() == "admin"
                has_global_permission = has_permission('global_access_scope', 'global_data_access')
                can_view_mobile = has_permission('leads', 'view_mobile') or is_admin or has_global_permission
                can_call = has_permission('leads', 'click_to_call') or is_admin or has_global_permission

                # Hierarchy allowed IDs for current logged user (includes self + all reporting team members)
                allowed_ids, _ = fetch_user_tree(cursor, logged_user_uuid)
                allowed_ids_set = set(allowed_ids or [])
                if user_id:
                    allowed_ids_set.add(user_id)

                user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
                last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, logged_user_uuid)

                # Determine search type and construct exact / specific WHERE clauses
                leads_where_clauses = []
                leads_params = []

                clients_where_clauses = []
                clients_params = []

                if search_query.isdigit():
                    num_val = int(search_query)
                    if len(search_query) <= 8:
                        # 1. Exact Lead ID / Client ID / Client Code Match
                        leads_where_clauses.append("l.id = %s")
                        leads_params.append(num_val)

                        clients_where_clauses.append("(c.id = %s OR c.lead_id = %s OR c.client_code = %s)")
                        clients_params.extend([num_val, num_val, search_query])
                    else:
                        # 2. Exact Mobile Number Match
                        leads_where_clauses.append("l.mobile_number = %s")
                        leads_params.append(search_query)

                        clients_where_clauses.append("(c.mobile_number = %s OR l.mobile_number = %s)")
                        clients_params.extend([search_query, search_query])

                elif "@" in search_query:
                    # 3. Email Search (Exact or domain match)
                    if "." in search_query.split("@")[-1]:
                        leads_where_clauses.append("(l.email = %s OR l.email LIKE %s)")
                        leads_params.extend([search_query, f"%{search_query}%"])

                        clients_where_clauses.append("(c.email = %s OR c.email LIKE %s OR l.email = %s OR l.email LIKE %s)")
                        clients_params.extend([search_query, f"%{search_query}%", search_query, f"%{search_query}%"])
                    else:
                        leads_where_clauses.append("l.email LIKE %s")
                        leads_params.append(f"%{search_query}%")

                        clients_where_clauses.append("(c.email LIKE %s OR l.email LIKE %s)")
                        clients_params.extend([f"%{search_query}%", f"%{search_query}%"])

                elif search_query.upper().startswith(("LED", "CLT", "CLI", "SO-", "SO")):
                    # 4. Exact UUID or Code Search
                    leads_where_clauses.append("l.lead_uuid = %s")
                    leads_params.append(search_query)

                    clients_where_clauses.append("(c.client_code = %s OR c.client_uuid = %s OR c.sales_order_uuid = %s OR l.lead_uuid = %s)")
                    clients_params.extend([search_query, search_query, search_query, search_query])

                else:
                    # 5. Name / Text Search
                    like_q = f"%{search_query}%"
                    leads_where_clauses.append("l.name LIKE %s")
                    leads_params.append(like_q)

                    clients_where_clauses.append("(c.client_name LIKE %s OR l.name LIKE %s)")
                    clients_params.extend([like_q, like_q])

                # 1. Query LEADS Table (EXCLUDING Paid / Converted Clients)
                where_leads_str = " OR ".join(leads_where_clauses)
                sql_leads = f"""
                    SELECT 
                        l.id, l.lead_uuid, l.name, l.mobile_number, l.email, l.address,
                        l.lead_source, ls.source_name AS source_name, ls.id AS source_id,
                        st.status_name AS status_name, st.id AS status_id, st.status_tone AS status_tone,
                        st.status_tone AS status_color,
                        l.lead_status, l.call_status, l.current_owner_user_id, l.created_by, l.lead_batch_id,
                        u.user_uuid AS owner_uuid, u.user_uuid AS user_uuid, u.full_name AS owner_name,
                        l.comment AS comment, l.is_disposed, l.disposed_by, l.disposed_at, l.created_at, l.updated_at, l.assigned_at,
                        (CASE WHEN EXISTS (SELECT 1 FROM contacts c WHERE c.lead_id = l.id) THEN 1 ELSE 0 END) AS has_contact,
                        (CASE WHEN EXISTS (SELECT 1 FROM followups f WHERE f.lead_id = l.id) THEN 1 ELSE 0 END) AS has_followup,
                        (CASE WHEN EXISTS (SELECT 1 FROM free_trials ft WHERE ft.lead_id = l.id) THEN 1 ELSE 0 END) AS has_free_trial,
                        0 AS has_so
                    FROM leads l
                    LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
                    LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_uuid = l.lead_status OR st.status_name = l.lead_status)
                    LEFT JOIN users u ON u.id = l.current_owner_user_id
                    WHERE ({where_leads_str})
                      AND NOT EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id AND so.order_status = 'approved')
                      AND NOT EXISTS (SELECT 1 FROM clients c WHERE c.lead_id = l.id)
                    ORDER BY l.id DESC 
                    LIMIT 50
                """
                cursor.execute(sql_leads, leads_params)
                raw_leads = cursor.fetchall() or []

                for r in raw_leads:
                    lead_owner_id = r.get("current_owner_user_id")
                    lead_creator_id = r.get("created_by")

                    has_access = (
                        is_admin 
                        or has_global_permission 
                        or (lead_owner_id and lead_owner_id in allowed_ids_set)
                        or (lead_creator_id and lead_creator_id in allowed_ids_set)
                    )

                    if has_access:
                        prep = prepare_lead_row(r, user_settings, last_dialed_lead_uuid)
                        if not can_call:
                            prep["click_to_call_active"] = False
                        prep["has_access"] = True
                        prep["is_disposed"] = 1 if (r.get("is_disposed") == 1 or r.get("disposed_by") or r.get("disposed_at")) else 0
                        leads_list.append(prep)
                    else:
                        # Restricted Lead View (Only ID, Name, and Owner)
                        leads_list.append({
                            "id": r["id"],
                            "lead_uuid": r["lead_uuid"],
                            "client_code": f"#{r['id']}",
                            "name": r.get("name") or "Unnamed Lead",
                            "email": "******",
                            "mobile_number": "******",
                            "mobile_display": "******",
                            "decrypted_mobile": "******",
                            "click_to_call_active": False,
                            "is_last_dialed": False,
                            "call_status": 0,
                            "status_name": "Protected",
                            "status_tone": "slate",
                            "status_color": "secondary",
                            "source_name": "—",
                            "owner_name": r.get("owner_name") or "Unassigned",
                            "comment": "—",
                            "latest_comment": "—",
                            "updated_at": "",
                            "has_contact": 0,
                            "has_followup": 0,
                            "has_free_trial": 0,
                            "has_so": 0,
                            "has_access": False
                        })

                # 2. Query CLIENTS Table (All Converted & Direct Clients)
                if clients_where_clauses:
                    where_clients_str = " OR ".join(clients_where_clauses)
                    sql_clients = f"""
                        SELECT 
                            c.id, c.client_uuid, c.client_code, c.client_name, c.mobile_number, c.email,
                            c.product_name, c.plan_name, c.total_amount, c.grand_total, c.so_status, c.client_status,
                            c.service_start_date, c.service_expiry_date, c.created_at, c.created_by_user_id, c.lead_id,
                            l.lead_uuid AS lead_uuid,
                            u.full_name AS owner_name, u.user_uuid AS owner_uuid,
                            mgr.full_name AS manager_name, mgr.user_uuid AS manager_uuid
                        FROM clients c
                        LEFT JOIN leads l ON l.id = c.lead_id
                        LEFT JOIN users u ON u.id = COALESCE(l.current_owner_user_id, c.created_by_user_id)
                        LEFT JOIN users mgr ON mgr.id = u.reporting_to_user_id
                        WHERE ({where_clients_str})
                        ORDER BY c.id DESC 
                        LIMIT 50
                    """
                    cursor.execute(sql_clients, clients_params)
                    raw_clients = cursor.fetchall() or []

                    for cr in raw_clients:
                        client_owner_id = cr.get("created_by_user_id")
                        has_access = (
                            is_admin 
                            or has_global_permission 
                            or (client_owner_id and client_owner_id in allowed_ids_set)
                        )

                        raw_mob = str(cr.get("mobile_number") or "").strip()
                        lead_uid = cr.get("lead_uuid") or cr.get("client_uuid")
                        if has_access:
                            disp_mob, dec_mob = format_mobile_display(raw_mob, user_settings)
                            clients_list.append({
                                "id": cr["id"],
                                "client_uuid": cr["client_uuid"],
                                "lead_uuid": lead_uid,
                                "client_code": cr.get("client_code") or f"CLT-{cr['id']}",
                                "client_name": cr.get("client_name") or "Unnamed Client",
                                "mobile_number": raw_mob,
                                "decrypted_mobile": dec_mob,
                                "mobile_display": disp_mob,
                                "click_to_call_active": can_call and bool(dec_mob and dec_mob != "NA"),
                                "is_last_dialed": False,
                                "call_status": 0,
                                "email": cr.get("email") or "N/A",
                                "product_name": cr.get("product_name") or "—",
                                "plan_name": cr.get("plan_name") or "—",
                                "service_start_date": str(cr.get("service_start_date"))[:10] if cr.get("service_start_date") else "—",
                                "service_expiry_date": str(cr.get("service_expiry_date"))[:10] if cr.get("service_expiry_date") else "—",
                                "total_payment": float(cr.get("grand_total") or cr.get("total_amount") or 0),
                                "owner_name": cr.get("owner_name") or "System",
                                "manager_name": cr.get("manager_name") or "—",
                                "client_status": cr.get("client_status") or "active",
                                "so_status": cr.get("so_status") or "approved",
                                "invoices": [],
                                "has_access": True
                            })
                        else:
                            clients_list.append({
                                "id": cr["id"],
                                "client_uuid": cr["client_uuid"],
                                "lead_uuid": cr.get("lead_id") or cr["client_uuid"],
                                "client_code": cr.get("client_code") or f"CLT-{cr['id']}",
                                "client_name": cr.get("client_name") or "Unnamed Client",
                                "mobile_number": "******",
                                "decrypted_mobile": "******",
                                "mobile_display": "******",
                                "click_to_call_active": False,
                                "is_last_dialed": False,
                                "call_status": 0,
                                "email": "******",
                                "product_name": "—",
                                "plan_name": "—",
                                "service_start_date": "—",
                                "service_expiry_date": "—",
                                "total_payment": 0,
                                "owner_name": cr.get("owner_name") or "System",
                                "manager_name": "—",
                                "client_status": "protected",
                                "so_status": "—",
                                "invoices": [],
                                "has_access": False
                            })

                # Fetch products & statuses for activity and action modals
                cursor.execute("SELECT id, product_name FROM products WHERE status = 1 ORDER BY product_name ASC")
                products = cursor.fetchall() or []

                cursor.execute("SELECT id, status_name, status_tone FROM lead_statuses WHERE status = 1 ORDER BY id ASC")
                statuses = cursor.fetchall() or []

                cursor.execute("SELECT id, user_uuid, full_name FROM users WHERE status = 1 ORDER BY full_name ASC")
                owners = cursor.fetchall() or []

                filters = [
                    {
                        "name": "status",
                        "label": "Status",
                        "options": [{"value": str(s["id"]), "label": s["status_name"]} for s in statuses]
                    }
                ]

                total_leads = len(leads_list)
                total_clients = len(clients_list)
                total_results = total_leads + total_clients

        except Exception as e:
            print("Error executing global search:", e)
            import traceback
            traceback.print_exc()
        finally:
            conn.close()

        return render_template(
            "search/global_search.html",
            search_query=search_query,
            leads=leads_list,
            clients=clients_list,
            products=products,
            statuses=statuses,
            filters=filters,
            owners=owners,
            total_leads=total_leads,
            total_clients=total_clients,
            total_results=total_results,
            active_group="search",
            active_page="global_search",
            page_title=f"Search: {search_query}",
            page_heading="Search Results"
        )

    @app.route("/search/activate-lead", methods=["POST"], endpoint="search_activate_lead")
    def search_activate_lead():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        lead_uuid = request.form.get("lead_uuid", "").strip()
        search_query = request.form.get("q", "").strip()

        if not lead_uuid:
            flash("Lead not found.", "danger")
            return redirect(url_for("global_search_page", q=search_query))

        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for("global_search_page", q=search_query))

        try:
            with conn.cursor() as cursor:
                user_info = session.get("user") or {}
                user_id = user_info.get("id")
                is_admin = bool(user_info.get("is_admin")) or str(user_info.get("role_name", "")).lower() == "admin"

                # Fetch lead
                cursor.execute("""
                    SELECT id, name, id AS client_code
                    FROM leads
                    WHERE lead_uuid = %s
                    LIMIT 1
                """, (lead_uuid,))
                lead = cursor.fetchone()

                if not lead:
                    flash("Lead not found or access denied.", "danger")
                    return redirect(url_for("global_search_page", q=search_query))

                lead_id = lead["id"]
                lead_name = lead.get("name") or "Lead"

                # Activate lead
                cursor.execute("""
                    UPDATE leads
                    SET is_disposed = 0,
                        disposed_by = NULL,
                        disposed_at = NULL,
                        comment = 'Lead activated successfully.',
                        updated_at = NOW()
                    WHERE id = %s
                """, (lead_id,))

                # Log activity
                import uuid as _uuid
                act_uuid = "ACT" + _uuid.uuid4().hex[:12].upper()
                cursor.execute("""
                    INSERT INTO lead_activities (activity_uuid, lead_id, user_id, action_type, comment)
                    VALUES (%s, %s, %s, 'Lead Activated', 'Activated from search page')
                """, (act_uuid, lead_id, user_id))

                conn.commit()
                flash(f"Lead '{lead_name}' has been activated successfully.", "success")

        except Exception as e:
            print("Error activating lead:", e)
            import traceback
            traceback.print_exc()
            flash("Something went wrong while activating the lead.", "danger")
        finally:
            conn.close()

        return redirect(url_for("global_search_page", q=search_query))
