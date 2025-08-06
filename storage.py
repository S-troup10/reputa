from supabase import create_client, Client
from datetime import datetime, timezone
# Replace with your real values
SUPABASE_URL = "https://gmpxcungtwhjrhygqvdk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdtcHhjdW5ndHdoanJoeWdxdmRrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQyODQ1NjIsImV4cCI6MjA2OTg2MDU2Mn0.T6FLVh783wgB0Sq6uAY1JHTjpYpkx0Wy7zVapxwA-zE"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def add(table, data):
    try:
        response = supabase.table(table).insert(data).execute()
        inserted_id = response.data[0]['id'] if response.data else None
        return {'success': True, 'id': inserted_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def fetch(table, filters=None, multi_filters=None, gte_filters=None):
    try:
        query = supabase.table(table).select('*')
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        if multi_filters:
            for key, value_list in multi_filters.items():
                query = query.in_(key, value_list)
        if gte_filters:
            for key, value in gte_filters.items():
                query = query.gte(key, value)
        return query.execute().data
    except Exception as e:
        print("Error in fetch:", e)
        return None


def validate(email, password):
    try:
        result = fetch("users", filters={"email": email, "password": password})
        if result and len(result) == 1:
            return True, result[0]
        return False, None
    except Exception as e:
        print("Login error:", e)
        return False, None





def delete_multiple(table, id_list):
    """
    Deletes multiple rows by ID from a Supabase table.

    Args:
        table (str): Table name.
        id_list (list): List of record IDs to delete.

    Returns:
        dict: Success or error message.
    """
    try:
        response = supabase.table(table).delete().in_("id", id_list).execute()
        return {'success': True, 'response': response}
    except Exception as e:
        return {'success': False, 'error': dict(e).get("message")}



def delete(table, record_id):
    """
    Deletes a row from the specified Supabase table by ID.

    Args:
        table (str): Table name.
        record_id (int or str): ID of the record to delete.

    Returns:
        dict: Success or error message.
    """
    try:
        response = supabase.table(table).delete().eq("id", record_id).execute()

        # If the data is empty, the record may not exist
        if not response.data:
            return {'success': False, 'error': 'Record not found'}

        return {'success': True}

    except Exception as e:
        print(f"Delete error on table '{table}': {e}")
        return {'error': str(e), 'success': False}




def bulk_update(table: str, rows: list[dict], primary_key: str):
    """
    Update many rows in `table` in one request.

    Args:
        table       (str)          : table name
        rows        (list[dict])   : list of row dictionaries (must all include primary_key)
        primary_key (str)          : name of the primary‑key column

    Returns:
        dict with:
            success (bool)
            updated (int)  – how many rows Supabase reports as updated
            skipped (int)  – rows skipped because they lacked the PK
            error   (str | None)
            data    (list | None) – rows returned from Supabase on success
    """
    try:
        if not rows:
            return {"success": False, "error": "No rows provided.", "updated": 0, "skipped": 0}

        # Split into valid / invalid rows
        valid_rows   = [r for r in rows if primary_key in r]
        skipped_rows = len(rows) - len(valid_rows)

        if not valid_rows:
            return {"success": False, "error": f"No rows contained primary key '{primary_key}'.",
                    "updated": 0, "skipped": skipped_rows}

        # 1‑call bulk upsert (update existing, ignore non‑matches)
        response = (
            supabase
            .table(table)
            .upsert(valid_rows, on_conflict=primary_key, ignore_duplicates=False)
            .execute()
        )

        # Supabase returns updated rows in .data
        updated_rows = len(response.data) if response.data else 0

        if response.error:
            return {"success": False, "error": str(response.error),
                    "updated": updated_rows, "skipped": skipped_rows}

        return {
            "success": True,
            "updated": updated_rows,
            "skipped": skipped_rows,
            "data":   response.data
        }

    except Exception as e:
        return {"success": False, "error": str(e), "updated": 0, "skipped": len(rows)}

    
    








        
            
            



def update_row_by_primary_key(table, data, primary_key):
    """
    Update one row in the table where primary_key = data[primary_key].

    Args:
        table (str): Table name
        data (dict): Fields to update (must include the primary key)
        primary_key (str): The name of the primary key column

    Returns:
        dict: Success status or error message
    """
    try:
        if primary_key not in data:
            raise ValueError(f"Missing primary key '{primary_key}' in data.")

        record = data.copy()
        key_value = record.pop(primary_key)

        response = supabase.table(table).update(record).eq(primary_key, key_value).execute()

        # Check if update affected any records
        if not response.data:
            return {'error': 'Record not found or nothing updated.', 'success': False}

        return {'success': True, 'data': response.data}

    except Exception as e:
        return {'error': str(e), 'success': False}





def bulk_update_by_field(table, filter_field, filter_values, update_data):
    """
    Perform a bulk update on a table where filter_field is in filter_values.

    Args:
        table (str): Table name.
        filter_field (str): Column to filter by (e.g., 'campaign_id').
        filter_values (list): List of values to match.
        update_data (dict): Fields and values to update.

    Returns:
        dict: Success status and response data or error message.
    """
    try:
        response = (
            supabase
            .table(table)
            .update(update_data)
            .in_(filter_field, filter_values)
            .execute()
        )

        return {'success': True, 'data': response.data}

    except Exception as e:
        return {'success': False, 'error': str(e)}

    
def upsert(table: str, data):
    """
    Performs a bulk upsert into the specified table using Supabase.

    Args:
        table (str): Table name as a string.
        data (List[Dict]): List of dictionaries representing rows to insert/update.

    Returns:
        dict: { success: bool, data: list (on success), error: str (on failure) }
    """
    try:
        if not data:
            raise ValueError("Data list is empty")

        response = supabase.table(table).upsert(data).execute()
        print('supabase response : ', response)
        # If response.data is None or empty, treat as failure
        if response:
            return {'success': True, 'data': response.data}
            
        return {'error': 'No data returned from upsert', 'success': False}


    except Exception as e:
        return {'error': str(e), 'success': False}

    

# Initialize the database

import httpx  # for network errors

def get_user_by_email(email):
    try:
        response = supabase.table("users").select("*").eq("email", email).limit(1).execute()
        print('server response:', response)

        # Check if response is successful and has a valid data field
        if hasattr(response, 'status_code') and response.status_code != 200:
            return False, f"Supabase error: Status code {response.status_code}"

        if not hasattr(response, 'data') or response.data is None:
            return False, "Supabase error: Invalid response format"

        if len(response.data) == 0:
            return False, "No user found with that email"

        return True, response.data[0]

    except httpx.ConnectError:
        return False, "Network error: Failed to connect to Supabase"
    except httpx.ReadTimeout:
        return False, "Network error: Supabase request timed out"
    except httpx.RequestError as e:
        return False, f"Network error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def get_business_settings(user_id):
    """Get business settings for a user"""
    try:
        response = supabase.table("business_settings").select("*").eq("user_id", user_id).limit(1).execute()
        if response.data and len(response.data) > 0:
            return True, response.data[0]
        return True, None
    except Exception as e:
        return False, str(e)


def save_business_settings(user_id, business_name, google_review_link):
    """Save or update business settings"""
    try:
        # Check if settings exist
        existing = supabase.table("business_settings").select("*").eq("user_id", user_id).execute()

        data = {
            "user_id": user_id,
            "business_name": business_name,
            "google_review_link": google_review_link,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        if existing.data and len(existing.data) > 0:
            # Update existing
            response = supabase.table("business_settings").update(data).eq("user_id", user_id).execute()
        else:
            # Create new
            data["created_at"] = datetime.now(timezone.utc).isoformat()
            response = supabase.table("business_settings").insert(data).execute()

        return {'success': True, 'data': response.data}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def save_review_submission(business_id, customer_name, customer_email, rating, review_text, review_type='public'):
    """Save a review submission"""
    try:
        data = {
            "business_id": business_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "rating": rating,
            "review_text": review_text,
            "review_type": review_type,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        response = supabase.table("reviews").insert(data).execute()
        return {'success': True, 'data': response.data}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_reviews_for_business(user_id, limit=50):
    """Get reviews for a business"""
    try:
        # First get the business_id
        business_settings = supabase.table("business_settings").select("id").eq("user_id", user_id).execute()
        if not business_settings.data:
            return {'success': True, 'data': []}

        business_id = business_settings.data[0]['id']

        response = supabase.table("reviews").select("*").eq("business_id", business_id).order("created_at", desc=True).limit(limit).execute()
        return {'success': True, 'data': response.data}
    except Exception as e:
        return {'success': False, 'error': str(e)}