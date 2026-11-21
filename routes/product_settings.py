import uuid
from utils.permissions import require_permission
from flask import render_template, request, jsonify, session, redirect, url_for, flash
from config import get_db_connection

from utils.product_helpers import PRODUCT_PLAN_DEFINITIONS

DURATION_SEGMENTS = [
    {"key": k, "label": v} for k, v in PRODUCT_PLAN_DEFINITIONS.items()
]


def register_product_routes(app):

    @require_permission('settings', 'system_controls')
    @app.route("/settings/system/products", methods=["GET"], endpoint="product_settings")
    def product_settings_page():
        if not session.get("user_uuid"):
            flash("Please log in to access Product Settings.", "warning")
            return redirect(url_for("login"))

        conn = get_db_connection()
        products = []
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, product_uuid, product_name, status,
                           weekly, two_weekly, monthly, two_monthly, quarterly,
                           six_monthly, nine_monthly, yearly, eighteen_monthly, twenty_four_monthly,
                           created_at
                    FROM products
                    ORDER BY id DESC
                """)
                product_rows = cursor.fetchall()

                for prod in product_rows:
                    active_count = 0
                    for seg in DURATION_SEGMENTS:
                        val = float(prod.get(seg["key"]) or 0)
                        if val > 0:
                            active_count += 1
                    prod["active_segments_count"] = active_count
                    products.append(prod)

        finally:
            conn.close()

        total_products = len(products)

        return render_template(
            "settings/products_settings.html",
            products=products,
            duration_segments=DURATION_SEGMENTS,
            total_products=total_products,
            active_group="settings",
            active_page="product_settings",
        )

    @require_permission('settings', 'system_controls')
    @app.route("/settings/system/products/add", methods=["GET", "POST"], endpoint="add_product_page")
    def add_product_page():
        if not session.get("user_uuid"):
            flash("Please log in to access Product Settings.", "warning")
            return redirect(url_for("login"))

        if request.method == "POST":
            product_name = str(request.form.get("product_name") or "").strip()
            status = int(request.form.get("status") or 1)

            if not product_name:
                flash("Product Name is required.", "warning")
                return redirect(url_for("add_product_page"))

            prices = {}
            for seg in DURATION_SEGMENTS:
                key = seg["key"]
                raw_val = request.form.get(f"price_{key}", 0.0)
                try:
                    p_val = float(raw_val or 0.0)
                except (ValueError, TypeError):
                    p_val = 0.0
                prices[key] = max(0.0, p_val)

            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM products WHERE product_name = %s LIMIT 1", (product_name,))
                    if cursor.fetchone():
                        flash(f"Product with name '{product_name}' already exists.", "warning")
                        return redirect(url_for("add_product_page"))

                    prod_uuid = f"PRD{uuid.uuid4().hex[:12].upper()}"
                    cursor.execute("""
                        INSERT INTO products (
                            product_uuid, product_name, status,
                            weekly, two_weekly, monthly, two_monthly,
                            quarterly, six_monthly, nine_monthly, yearly,
                            eighteen_monthly, twenty_four_monthly
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        prod_uuid, product_name, status,
                        prices["weekly"], prices["two_weekly"], prices["monthly"], prices["two_monthly"],
                        prices["quarterly"], prices["six_monthly"], prices["nine_monthly"], prices["yearly"],
                        prices["eighteen_monthly"], prices["twenty_four_monthly"]
                    ))

                    conn.commit()
                flash(f"Product '{product_name}' created successfully.", "success")
                return redirect(url_for("product_settings"))
            except Exception as err:
                flash(f"Error creating product: {str(err)}", "danger")
                return redirect(url_for("add_product_page"))
            finally:
                conn.close()

        return render_template(
            "settings/product_form.html",
            product=None,
            duration_segments=DURATION_SEGMENTS,
            page_title="Add New Product",
            active_group="settings",
            active_page="product_settings",
        )

    @require_permission('settings', 'system_controls')
    @app.route("/settings/system/products/edit/<int:product_id>", methods=["GET", "POST"], endpoint="edit_product_page")
    def edit_product_page(product_id):
        if not session.get("user_uuid"):
            flash("Please log in to access Product Settings.", "warning")
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, product_uuid, product_name, status,
                           weekly, two_weekly, monthly, two_monthly, quarterly,
                           six_monthly, nine_monthly, yearly, eighteen_monthly, twenty_four_monthly
                    FROM products WHERE id = %s LIMIT 1
                """, (product_id,))
                product = cursor.fetchone()

                if not product:
                    flash("Product not found.", "warning")
                    return redirect(url_for("product_settings"))
        finally:
            conn.close()

        if request.method == "POST":
            product_name = str(request.form.get("product_name") or "").strip()
            status = int(request.form.get("status") or 1)

            if not product_name:
                flash("Product Name is required.", "warning")
                return redirect(url_for("edit_product_page", product_id=product_id))

            prices = {}
            for seg in DURATION_SEGMENTS:
                key = seg["key"]
                raw_val = request.form.get(f"price_{key}", 0.0)
                try:
                    p_val = float(raw_val or 0.0)
                except (ValueError, TypeError):
                    p_val = 0.0
                prices[key] = max(0.0, p_val)

            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM products WHERE product_name = %s AND id != %s LIMIT 1", (product_name, product_id))
                    if cursor.fetchone():
                        flash(f"Another product with name '{product_name}' already exists.", "warning")
                        return redirect(url_for("edit_product_page", product_id=product_id))

                    cursor.execute("""
                        UPDATE products
                        SET product_name = %s, status = %s,
                            weekly = %s, two_weekly = %s, monthly = %s, two_monthly = %s,
                            quarterly = %s, six_monthly = %s, nine_monthly = %s, yearly = %s,
                            eighteen_monthly = %s, twenty_four_monthly = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (
                        product_name, status,
                        prices["weekly"], prices["two_weekly"], prices["monthly"], prices["two_monthly"],
                        prices["quarterly"], prices["six_monthly"], prices["nine_monthly"], prices["yearly"],
                        prices["eighteen_monthly"], prices["twenty_four_monthly"],
                        product_id
                    ))

                    conn.commit()
                flash(f"Product '{product_name}' updated successfully.", "success")
                return redirect(url_for("product_settings"))
            except Exception as err:
                flash(f"Error updating product: {str(err)}", "danger")
                return redirect(url_for("edit_product_page", product_id=product_id))
            finally:
                conn.close()

        return render_template(
            "settings/product_form.html",
            product=product,
            duration_segments=DURATION_SEGMENTS,
            page_title="Edit Product",
            active_group="settings",
            active_page="product_settings",
        )

    @require_permission('settings', 'system_controls')
    @app.route("/settings/system/api/products/delete", methods=["POST"], endpoint="api_delete_product")
    def api_delete_product():
        if not session.get("user_uuid"):
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        payload = request.get_json(silent=True) or {}
        product_id = payload.get("product_id")

        if not product_id:
            return jsonify({"success": False, "message": "Product ID is required."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
                conn.commit()
            return jsonify({"success": True, "message": "Product deleted successfully."}), 200
        except Exception as err:
            return jsonify({"success": False, "message": str(err)}), 500
        finally:
            conn.close()
