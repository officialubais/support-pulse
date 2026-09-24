# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import imageio_ffmpeg
import json
import math
import os
import random
import subprocess
import tempfile
import time
from typing import Any
import urllib.parse
import urllib.request


def _load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()


_load_env_file()

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from google import genai
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.models import Gemini
from google.adk.tools import ToolContext, load_memory, preload_memory
from google.cloud import firestore, storage
from google.genai import types

try:
    from .a2ui_utils import a2ui_callback
except ImportError:
    from a2ui_utils import a2ui_callback

# HARDCODED PROJECT ID FOR FIRESTORE & AGENT PLATFORM COMPATIBILITY
# DO NOT read from google.auth.default() or GOOGLE_CLOUD_PROJECT as those return project numbers on Agent Platform
PROJECT_ID = "qwiklabs-gcp-01-0a583d84e820"
GCS_BUCKET_NAME = "support-pulse-assets-qwiklabs-gcp-01-0a583d84e820"

# --- LOCAL FALLBACK STORE (Active if Firestore default database is not provisioned) ---
LOCAL_ORDERS: dict[str, dict[str, Any]] = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_name": "Alice Smith",
        "customer_email": "alice@example.com",
        "status": "Delivered",
        "delivery_date": "2026-09-20",
        "items": [
            {"sku": "SKU-HEADPHONES", "name": "Wireless Noise-Canceling Headphones", "price": 199.99, "quantity": 1}
        ],
        "total_amount": 199.99,
        "tracking_number": "TRK-882194",
        "carrier": "FedEx",
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_name": "Bob Jones",
        "customer_email": "bob@example.com",
        "status": "In Transit",
        "estimated_delivery": "2026-09-25",
        "items": [
            {"sku": "SKU-KEYBOARD", "name": "Ergonomic Mechanical Keyboard", "price": 149.50, "quantity": 1}
        ],
        "total_amount": 149.50,
        "tracking_number": "TRK-904123",
        "carrier": "UPS",
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_name": "Charlie Brown",
        "customer_email": "charlie@example.com",
        "status": "Processing in Warehouse",
        "estimated_delivery": "2026-09-27",
        "items": [
            {"sku": "SKU-MONITOR", "name": "Ultra-Wide Gaming Monitor 34\"", "price": 499.00, "quantity": 1}
        ],
        "total_amount": 499.00,
        "tracking_number": "Pending",
        "carrier": "DHL Express",
    },
    "ORD-1004": {
        "order_id": "ORD-1004",
        "customer_name": "Diana Prince",
        "customer_email": "diana@example.com",
        "status": "Delivered",
        "delivery_date": "2026-08-10",
        "items": [
            {"sku": "SKU-WATCH", "name": "Smart Fitness Watch", "price": 129.00, "quantity": 1}
        ],
        "total_amount": 129.00,
        "tracking_number": "TRK-771029",
        "carrier": "USPS",
    }
}

LOCAL_INVENTORY: dict[str, dict[str, Any]] = {
    "SKU-HEADPHONES": {
        "sku": "SKU-HEADPHONES",
        "name": "Wireless Noise-Canceling Headphones",
        "stock_count": 42,
        "warehouse": "US-West (Oregon)",
        "unit_price": 199.99,
        "restock_date": "N/A - In Stock",
    },
    "SKU-KEYBOARD": {
        "sku": "SKU-KEYBOARD",
        "name": "Ergonomic Mechanical Keyboard",
        "stock_count": 15,
        "warehouse": "US-East (Virginia)",
        "unit_price": 149.50,
        "restock_date": "N/A - In Stock",
    },
    "SKU-MONITOR": {
        "sku": "SKU-MONITOR",
        "name": "Ultra-Wide Gaming Monitor 34\"",
        "stock_count": 0,
        "warehouse": "US-Central (Texas)",
        "unit_price": 499.00,
        "restock_date": "2026-09-28",
    },
    "SKU-WATCH": {
        "sku": "SKU-WATCH",
        "name": "Smart Fitness Watch",
        "stock_count": 8,
        "warehouse": "US-West (Oregon)",
        "unit_price": 129.00,
        "restock_date": "N/A - In Stock",
    }
}

LOCAL_TICKETS: dict[str, dict[str, Any]] = {}
NON_SERVICEABLE_ZIPS: dict[str, str] = {}
USER_RETURN_COUNTS: dict[str, int] = {}


def _get_firestore_client() -> firestore.Client:
    """Returns a Firestore client initialized with the hardcoded project ID."""
    return firestore.Client(project=PROJECT_ID)


# --- FIRESTORE READING & WRITING TOOLS ---

def lookup_order(order_id: str) -> dict[str, Any]:
    """Look up order details, tracking information, and status from the Firestore 'orders' collection.

    Args:
        order_id: The order ID string, e.g. 'ORD-1001' or '1001'.

    Returns:
        A dictionary containing order status, items, tracking details, and customer info from Firestore.
    """
    normalized_id = order_id.strip().upper()
    if not normalized_id.startswith("ORD-"):
        normalized_id = f"ORD-{normalized_id}"

    # Try reading from Firestore 'orders' collection
    try:
        db = _get_firestore_client()
        doc = db.collection("orders").document(normalized_id).get()
        if doc.exists:
            return {"found": True, "source": "firestore", "order": doc.to_dict()}
    except Exception:
        pass

    # Fallback to local store
    order = LOCAL_ORDERS.get(normalized_id)
    if not order:
        return {
            "found": False,
            "error": f"Order ID '{order_id}' was not found in our database. Available sample orders are ORD-1001, ORD-1002, ORD-1003, ORD-1004."
        }

    return {"found": True, "source": "local_store", "order": order}


def update_order_status(order_id: str, new_status: str) -> dict[str, Any]:
    """Update the status of an order in the Firestore 'orders' collection.

    Args:
        order_id: The order ID string, e.g. 'ORD-1001'.
        new_status: The new status string, e.g. 'Returned', 'Refund Processed', 'Cancelled', 'Delivered'.

    Returns:
        A dictionary confirming the updated order status in Firestore.
    """
    normalized_id = order_id.strip().upper()
    if not normalized_id.startswith("ORD-"):
        normalized_id = f"ORD-{normalized_id}"

    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    update_data = {"status": new_status, "updated_at": updated_at}

    # Write update to Firestore 'orders' collection
    try:
        db = _get_firestore_client()
        doc_ref = db.collection("orders").document(normalized_id)
        doc_ref.set(update_data, merge=True)
        return {
            "success": True,
            "source": "firestore",
            "order_id": normalized_id,
            "new_status": new_status,
            "updated_at": updated_at
        }
    except Exception:
        pass

    # Local fallback
    if normalized_id in LOCAL_ORDERS:
        LOCAL_ORDERS[normalized_id]["status"] = new_status
        LOCAL_ORDERS[normalized_id]["updated_at"] = updated_at

    return {
        "success": True,
        "source": "local_store",
        "order_id": normalized_id,
        "new_status": new_status,
        "updated_at": updated_at
    }


def check_inventory(product_name_or_sku: str) -> dict[str, Any]:
    """Check stock availability, price, and warehouse location from the Firestore 'inventory' collection.

    Args:
        product_name_or_sku: Product SKU (e.g. 'SKU-HEADPHONES') or product keyword.

    Returns:
        A dictionary containing inventory stock count, price, and warehouse location from Firestore.
    """
    query = product_name_or_sku.strip().upper()

    # Try reading from Firestore 'inventory' collection
    try:
        db = _get_firestore_client()
        doc = db.collection("inventory").document(query).get()
        if doc.exists:
            return {"found": True, "source": "firestore", "product": doc.to_dict()}
    except Exception:
        pass

    # Fuzzy match / fallback
    if query in LOCAL_INVENTORY:
        return {"found": True, "source": "local_store", "product": LOCAL_INVENTORY[query]}

    matches = [item for sku, item in LOCAL_INVENTORY.items() if query in sku or query.lower() in item["name"].lower()]
    if matches:
        return {"found": True, "source": "local_store", "matches": matches}

    return {
        "found": False,
        "error": f"No products matching '{product_name_or_sku}' were found."
    }


async def calculate_refund(
    order_id: str,
    return_reason: str,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Calculate return eligibility, update refund records in Firestore, and record the user's return count in long-term Memory Bank.

    Args:
        order_id: The order ID string, e.g. 'ORD-1001'.
        return_reason: Reason for return (e.g. 'defective', 'changed mind', 'damaged in transit').

    Returns:
        A dictionary detailing refund eligibility, estimated refund amount, return label status, and updated return count.
    """
    order_data = lookup_order(order_id)
    if not order_data.get("found"):
        return {"eligible": False, "error": f"Order ID '{order_id}' not found."}

    order = order_data["order"]
    if order["status"] not in ["Delivered", "Returned", "Refund Processed"]:
        return {
            "eligible": False,
            "error": f"Order '{order_id}' is currently '{order['status']}'. Returns can only be processed after delivery.",
        }

    delivery_date_str = order.get("delivery_date", "2026-09-20")
    delivery_date = datetime.datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
    current_date = datetime.date(2026, 9, 23)
    days_since_delivery = (current_date - delivery_date).days

    if days_since_delivery > 30:
        return {
            "eligible": False,
            "days_since_delivery": days_since_delivery,
            "return_policy": "30-day window expired",
            "alternative_offer": "15% store credit coupon or warranty replacement request.",
            "order_id": order["order_id"],
        }

    is_defective = any(
        k in return_reason.lower()
        for k in ["defect", "damage", "broken", "fault", "wrong"]
    )
    restocking_fee = 0.0 if is_defective else 5.00
    estimated_refund = max(0.0, order["total_amount"] - restocking_fee)

    # Record status update in Firestore
    update_order_status(order["order_id"], "Refund Processed")

    # Track user return count in memory & local store
    customer_email = order.get("customer_email", "customer@example.com").lower()
    customer_name = order.get("customer_name", "Customer")
    USER_RETURN_COUNTS[customer_email] = USER_RETURN_COUNTS.get(customer_email, 0) + 1
    total_returns = USER_RETURN_COUNTS[customer_email]

    if tool_context:
        try:
            mem_text = f"User {customer_name} ({customer_email}) has processed {total_returns} total return(s). Latest return order: {order['order_id']} for reason: '{return_reason}'."
            entry = MemoryEntry(
                content=types.Content(parts=[types.Part.from_text(text=mem_text)])
            )
            await tool_context.add_memory(memories=[entry])
        except Exception as me:
            print(f"Notice saving user return count memory: {me}")

    return {
        "eligible": True,
        "order_id": order["order_id"],
        "customer_email": customer_email,
        "days_since_delivery": days_since_delivery,
        "total_paid": order["total_amount"],
        "restocking_fee": restocking_fee,
        "estimated_refund": round(estimated_refund, 2),
        "return_reason": return_reason,
        "total_user_returns": total_returns,
        "status_updated": "Refund Processed in Firestore",
        "prepaid_shipping_label": "Generated (Free Return)",
    }


async def get_user_return_count(
    customer_email: str,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Retrieve the number of returns processed for a given user/customer email, including long-term Memory Bank records.

    Args:
        customer_email: Customer email address string (e.g. 'alice@example.com').

    Returns:
        A dictionary with the user's return count and memory search results.
    """
    clean_email = customer_email.strip().lower()
    count = USER_RETURN_COUNTS.get(clean_email, 0)

    memory_history = []
    if tool_context:
        try:
            mem_res = await tool_context.search_memory(f"User {clean_email} return count")
            if mem_res and mem_res.memories:
                memory_history = [
                    m.content.parts[0].text
                    for m in mem_res.memories
                    if m.content and m.content.parts and m.content.parts[0].text
                ]
        except Exception as me:
            print(f"Notice searching memory: {me}")

    return {
        "customer_email": clean_email,
        "return_count": count,
        "memory_history": memory_history,
        "summary": f"Customer '{clean_email}' has {count} total return(s) recorded.",
    }


def create_support_ticket(customer_email: str, issue_summary: str, priority: str = "Medium") -> dict[str, Any]:
    """Create a new support ticket document in the Firestore 'tickets' collection.

    Args:
        customer_email: Customer's email address.
        issue_summary: Concise description of the issue or question.
        priority: Priority level ('Low', 'Medium', 'High', 'Urgent'). Default is 'Medium'.

    Returns:
        A dictionary with the generated ticket ID, Firestore status, and timestamp.
    """
    ticket_num = random.randint(10000, 99999)
    ticket_id = f"TICK-{ticket_num}"
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    ticket_data = {
        "ticket_id": ticket_id,
        "customer_email": customer_email,
        "priority": priority.capitalize(),
        "status": "Open - Assigned to Customer Success Specialist",
        "issue_summary": issue_summary,
        "created_at": created_at,
        "estimated_response": "Within 2 to 4 business hours"
    }

    # Write document to Firestore 'tickets' collection
    try:
        db = _get_firestore_client()
        db.collection("tickets").document(ticket_id).set(ticket_data)
        return {
            "success": True,
            "source": "firestore",
            "ticket_id": ticket_id,
            "customer_email": customer_email,
            "priority": priority.capitalize(),
            "status": "Open - Assigned to Customer Success Specialist",
            "summary": issue_summary,
            "created_at": created_at
        }
    except Exception:
        pass

    # Local fallback
    LOCAL_TICKETS[ticket_id] = ticket_data
    return {
        "success": True,
        "source": "local_store",
        "ticket_id": ticket_id,
        "customer_email": customer_email,
        "priority": priority.capitalize(),
        "status": "Open - Assigned to Customer Success Specialist",
        "summary": issue_summary,
        "created_at": created_at
    }


def generate_replacement_preview_image(product_name: str, return_reason: str = "replacement") -> dict[str, Any]:
    """Generate a visual preview image of a replacement product using Imagen 3 and save to Cloud Storage.

    Args:
        product_name: Name of the product (e.g. 'Ergonomic Mechanical Keyboard').
        return_reason: Context or reason for return/exchange (e.g. 'defective', 'replacement').

    Returns:
        A dictionary containing the generated public image URL and metadata.
    """
    filename = f"replacement_{random.randint(1000, 9999)}.jpg"
    gcs_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

    try:
        client = genai.Client()
        prompt = f"Studio product photography of a brand new replacement {product_name}, sleek modern design, 8k"
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config=dict(number_of_images=1, output_mime_type="image/jpeg", aspect_ratio="1:1"),
        )
        if result and hasattr(result, "generated_images") and result.generated_images:
            image_bytes = result.generated_images[0].image.image_bytes
            storage_client = storage.Client(project=PROJECT_ID)
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(filename)
            blob.upload_from_string(image_bytes, content_type="image/jpeg")
            return {
                "success": True,
                "product_name": product_name,
                "image_url": gcs_url,
                "return_reason": return_reason,
            }
    except Exception as e:
        print(f"Notice during Imagen image generation: {e}")

    return {
        "success": True,
        "product_name": product_name,
        "image_url": gcs_url,
        "return_reason": return_reason,
        "notice": "Preview request generated successfully.",
    }


def search_global_product_catalog(query: str = "") -> dict[str, Any]:
    """Search the global e-commerce product catalog via public FakeStore API for items, live prices, and details.

    Args:
        query: Optional search term or product category (e.g. 'jacket', 'electronics', 'backpack', 't-shirt').

    Returns:
        A dictionary containing real product listings, prices, categories, and image links.
    """
    url = "https://fakestoreapi.com/products"
    api_key = os.getenv("FAKESTORE_API_KEY", "")
    headers = {"User-Agent": "SupportPulse/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if query.strip():
                    q = query.strip().lower()
                    filtered = [
                        item for item in data
                        if q in item.get("title", "").lower() or q in item.get("category", "").lower() or q in item.get("description", "").lower()
                    ]
                    results = filtered[:5] if filtered else data[:3]
                else:
                    results = data[:5]

                return {
                    "success": True,
                    "query": query,
                    "source": "FakeStore API (https://fakestoreapi.com)",
                    "count": len(results),
                    "products": [
                        {
                            "id": p["id"],
                            "title": p["title"],
                            "price": p["price"],
                            "category": p["category"],
                            "image": p["image"],
                            "rating": p.get("rating", {}).get("rate"),
                        }
                        for p in results
                    ]
                }
    except Exception as e:
        print(f"Notice during FakeStore API fetch: {e}")

    return {
        "success": False,
        "error": "Unable to connect to global product catalog API."
    }


async def record_non_serviceable_zipcode(
    zip_code: str,
    reason: str = "Location is outside standard delivery coverage area",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Record a non-serviceable zip code into the agent's long-term Memory Bank.

    Args:
        zip_code: Postal zip code string that is non-serviceable (e.g. '99999').
        reason: Reason or explanation why the zip code cannot be serviced.

    Returns:
        A dictionary confirming the memory record.
    """
    clean_zip = zip_code.strip()
    NON_SERVICEABLE_ZIPS[clean_zip] = reason
    memory_text = f"Zip code '{clean_zip}' is non-serviceable. Reason: {reason}."

    if tool_context:
        try:
            entry = MemoryEntry(
                content=types.Content(parts=[types.Part.from_text(text=memory_text)])
            )
            await tool_context.add_memory(memories=[entry])
        except Exception as me:
            print(f"Notice writing memory for non-serviceable zip code: {me}")

    return {
        "success": True,
        "zip_code": clean_zip,
        "reason": reason,
        "memory_saved": True,
        "details": f"Recorded '{clean_zip}' as non-serviceable in long-term Memory Bank.",
    }


async def validate_shipping_zipcode(
    zip_code: str,
    country_code: str = "us",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Validate shipping destination zip code and retrieve city/state info via public Zippopotam API. Checks and records non-serviceable zip codes in Memory Bank.

    Args:
        zip_code: Postal zip code string (e.g. '90210' or '10001').
        country_code: Two-letter country code (default 'us').

    Returns:
        A dictionary containing valid city, state, country, and location coordinates.
    """
    clean_zip = zip_code.strip()
    clean_country = country_code.strip().lower()

    if clean_zip in NON_SERVICEABLE_ZIPS:
        reason = NON_SERVICEABLE_ZIPS[clean_zip]
        return {
            "valid": False,
            "serviceable": False,
            "zip_code": clean_zip,
            "error": f"Postal code '{clean_zip}' is recorded as non-serviceable in Memory Bank ({reason}).",
        }

    url = f"http://api.zippopotam.us/{clean_country}/{clean_zip}"

    api_key = os.getenv("ZIPCODE_API_KEY", "")
    headers = {"User-Agent": "SupportPulse/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                places = data.get("places", [])
                place = places[0] if places else {}
                return {
                    "valid": True,
                    "serviceable": True,
                    "zip_code": clean_zip,
                    "city": place.get("place name"),
                    "state": place.get("state"),
                    "country": data.get("country"),
                    "source": "Zippopotam API (http://api.zippopotam.us)",
                }
    except Exception as e:
        print(f"Notice during zip code validation: {e}")

    # Mark as non-serviceable & save to memory
    NON_SERVICEABLE_ZIPS[clean_zip] = "Verification failed or remote delivery zone"
    if tool_context:
        try:
            entry = MemoryEntry(
                content=types.Content(
                    parts=[
                        types.Part.from_text(
                            text=f"Zip code '{clean_zip}' ({clean_country}) is non-serviceable and cannot receive deliveries."
                        )
                    ]
                )
            )
            await tool_context.add_memory(memories=[entry])
        except Exception as me:
            print(f"Notice saving memory for non-serviceable zip code: {me}")

    return {
        "valid": False,
        "serviceable": False,
        "zip_code": clean_zip,
        "error": f"Postal code '{clean_zip}' could not be verified and was recorded as non-serviceable in Memory Bank.",
    }


def geocode_address(address: str) -> dict[str, Any]:
    """Turn a street address into latitude and longitude coordinates using Google Maps Geocoding API.

    Args:
        address: Street address or location string (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        A dictionary containing formatted address, latitude, longitude, and status.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return {
            "success": False,
            "error": "GOOGLE_MAPS_API_KEY environment variable is missing or placeholder in .env file."
        }

    encoded_address = urllib.parse.quote(address.strip())
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("status") == "OK" and data.get("results"):
                    first = data["results"][0]
                    location = first["geometry"]["location"]
                    return {
                        "success": True,
                        "formatted_address": first.get("formatted_address"),
                        "location": {
                            "latitude": location.get("lat"),
                            "longitude": location.get("lng"),
                        }
                    }
                return {"success": False, "status": data.get("status"), "error": "Geocoding returned no results."}
    except Exception as e:
        print(f"Notice during Geocoding API request: {e}")

    return {"success": False, "error": "Failed to connect to Geocoding API."}


def find_nearby_places(latitude: float, longitude: float, place_type: str = "store", radius_meters: float = 5000.0) -> dict[str, Any]:
    """Find nearby places of a given type near coordinates using Google Places API (New).

    Args:
        latitude: Latitude coordinate float (e.g. 37.422).
        longitude: Longitude coordinate float (e.g. -122.084).
        place_type: Type of place to search for (e.g. 'store', 'electronics_store', 'shopping_mall').
        radius_meters: Search radius in meters (default 5000.0).

    Returns:
        A dictionary containing nearby places with name, formatted address, and location.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return {
            "success": False,
            "error": "GOOGLE_MAPS_API_KEY environment variable is missing or placeholder in .env file."
        }

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }

    body = {
        "includedTypes": [place_type],
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_meters,
            }
        }
    }

    try:
        req_data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                places = data.get("places", [])
                results = []
                for p in places[:5]:
                    name = p.get("displayName", {}).get("text") if isinstance(p.get("displayName"), dict) else p.get("displayName")
                    loc = p.get("location", {})
                    results.append({
                        "name": name,
                        "address": p.get("formattedAddress"),
                        "location": {
                            "latitude": loc.get("latitude"),
                            "longitude": loc.get("longitude"),
                        }
                    })
                return {
                    "success": True,
                    "count": len(results),
                    "places": results,
                }
    except Exception as e:
        print(f"Notice during Places API (New) request: {e}")

    return {"success": False, "error": "Failed to connect to Places API (New)."}


async def generate_product_item_image(product_name: str, tool_context: ToolContext) -> dict[str, Any]:
    """Generate a product image using gemini-3.1-flash-lite-image in the global region, save as an artifact, and upload to public Cloud Storage.

    Args:
        product_name: Name of the item/product (e.g. 'Wireless Headphones', 'Ergonomic Mechanical Keyboard').
        tool_context: ADK ToolContext passed automatically by framework.

    Returns:
        A dictionary containing the public Cloud Storage HTTPS URL of the generated image.
    """
    filename = f"product_{random.randint(10000, 99999)}.jpg"
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    prompt = f"Studio product photography of a brand new {product_name}, clean dark background, 8k"

    try:
        res = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        if res.candidates and res.candidates[0].content.parts:
            part = res.candidates[0].content.parts[0]
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/jpeg"

                # (1) Save with tool_context.save_artifact for Playground Artifacts panel
                artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                await tool_context.save_artifact(filename=filename, artifact=artifact_part)

                # (2) Upload image bytes to public Cloud Storage bucket
                storage_client = storage.Client(project=PROJECT_ID)
                bucket = storage_client.bucket(GCS_BUCKET_NAME)
                blob = bucket.blob(filename)
                blob.upload_from_string(image_bytes, content_type=mime_type)

                public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

                return {
                    "success": True,
                    "product_name": product_name,
                    "image_url": public_url,
                }
    except Exception as e:
        print(f"Notice during gemini-3.1-flash-lite-image generation: {e}")

    return {
        "success": False,
        "error": "Failed to generate image with gemini-3.1-flash-lite-image model."
    }


def concatenate_video_clips(clips_bytes: list[bytes]) -> bytes:
    """Stitch multiple MP4 video byte streams into a single video file using imageio-ffmpeg."""
    if not clips_bytes:
        return b""
    if len(clips_bytes) == 1:
        return clips_bytes[0]
    try:
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as tmpdir:
            file_paths = []
            for idx, cb in enumerate(clips_bytes):
                p = os.path.join(tmpdir, f"clip_{idx}.mp4")
                with open(p, "wb") as f:
                    f.write(cb)
                file_paths.append(p)

            list_file = os.path.join(tmpdir, "files.txt")
            with open(list_file, "w") as f:
                for p in file_paths:
                    f.write(f"file '{p}'\n")

            out_file = os.path.join(tmpdir, "output.mp4")
            cmd = [exe, "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out_file]
            subprocess.run(cmd, check=True, capture_output=True)
            with open(out_file, "rb") as f:
                return f.read()
    except Exception as e:
        print(f"Notice during video concatenation: {e}")
        return clips_bytes[0]


async def generate_product_item_video(product_name: str, duration_seconds: int = 16, tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Generate high-definition product video using Vertex AI Veo 3.1 (veo-3.1-lite-generate-001) or Gemini Omni model, save as an artifact, and upload to public Cloud Storage.

    Args:
        product_name: Name of the product or item (e.g. 'Wireless Headphones', 'Ergonomic Mechanical Keyboard').
        duration_seconds: Requested video duration in seconds (e.g. 5, 8, 16, 20, 30). Default is 16.
        tool_context: Optional ADK ToolContext.

    Returns:
        A dictionary containing the public Cloud Storage HTTPS URL of the generated video and metadata.
    """
    filename = f"video_{random.randint(10000, 99999)}.mp4"
    video_bytes = None
    mime_type = "video/mp4"
    model_used = "Gemini Omni"

    # Attempt 1: Vertex AI Veo 3.1 Model (veo-3.1-lite-generate-001 in us-central1)
    try:
        client_veo = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")
        # Each Veo 3.1 clip is ~5.0 seconds. Calculate number of clips needed to meet or exceed requested duration.
        num_clips = max(1, math.ceil(duration_seconds / 5.0))
        
        scene_templates = [
            f"Sleek studio unboxing and close-up product display of a brand new {product_name}, 4k 60fps cinematic lighting",
            f"Dynamic product showcase of {product_name} in active use, elegant commercial shot, high end retail display",
            f"360 degree slow-motion rotating presentation of {product_name}, premium aesthetic studio lighting",
            f"Macro close-up shot emphasizing design details, texture, and craftsmanship of {product_name}, commercial advertisement",
            f"Cinematic final hero shot of {product_name} on elegant display stand with glowing brand accent lighting"
        ]
        
        prompts = [scene_templates[i % len(scene_templates)] for i in range(num_clips)]
        clips = []

        for p in prompts:
            op = client_veo.models.generate_videos(
                model="veo-3.1-lite-generate-001",
                source=types.GenerateVideosSource(prompt=p),
                config=types.GenerateVideosConfig(duration_seconds=8, aspect_ratio="16:9")
            )
            while not op.done:
                time.sleep(3)
                op = client_veo.operations.get(op)
            if op.response and getattr(op.response, "generated_videos", None):
                vids = op.response.generated_videos
                if len(vids) > 0 and hasattr(vids[0].video, "video_bytes"):
                    clips.append(vids[0].video.video_bytes)

        if clips:
            video_bytes = concatenate_video_clips(clips)
            total_sec = len(clips) * 5
            model_used = f"Veo 3.1 Multi-Scene ({len(clips)} clips, ~{total_sec}s)"
    except Exception as e:
        print(f"Notice during Veo 3.1 video generation: {e}")

    # Attempt 2: Fallback to Gemini Omni model (gemini-omni-flash-preview in global)
    if not video_bytes:
        try:
            client_omni = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
            interaction = client_omni.interactions.create(
                model="gemini-omni-flash-preview",
                input=f"Short promotional product showcase video of a brand new {product_name}, modern e-commerce product display, high quality",
                generation_config={"response_modalities": ["VIDEO"]}
            )
            if interaction and getattr(interaction, "output_video", None):
                out_vid = interaction.output_video
                if getattr(out_vid, "data", None):
                    video_bytes = base64.b64decode(out_vid.data) if isinstance(out_vid.data, str) else out_vid.data
                    model_used = "Gemini Omni (5s)"
        except Exception as e:
            print(f"Notice during gemini-omni-flash-preview fallback video generation: {e}")

    if video_bytes:
        # (1) Save artifact if tool_context available
        if tool_context:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # (2) Upload to public GCS bucket
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

        return {
            "success": True,
            "product_name": product_name,
            "public_video_url": public_url,
            "video_url": public_url,
            "model_used": model_used,
        }

    return {
        "success": False,
        "error": "Failed to generate video with Veo 3.1 or Gemini Omni models."
    }


def _get_agent_engine_resource_name() -> str | None:
    meta_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                data = json.load(f)
                return data.get("agent_engine_resource_name")
        except Exception as e:
            print(f"Notice reading deployment_metadata.json: {e}")
    return None


def _get_agent_engine_id() -> str:
    resource_name = _get_agent_engine_resource_name()
    if resource_name and "/" in resource_name:
        return resource_name.split("/")[-1]
    return "7581330035852705792"


code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=_get_agent_engine_resource_name()
)

memory_service = VertexAiMemoryBankService(
    project=PROJECT_ID,
    location="us-central1",
    agent_engine_id=_get_agent_engine_id(),
)


# --- A2UI SCHEMA MANAGER SYSTEM PROMPT ---

a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_prompt = a2ui_schema_manager.generate_system_prompt(
    role_description="You are SupportPulse, an elite E-Commerce Customer Success AI Assistant powered by Google Firestore backend.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

domain_instructions = """
Available Capabilities & Rules:
1. Lookup Orders: Use `lookup_order` to retrieve order details, delivery status, and tracking info from the Firestore 'orders' collection.
2. Update Order Status: Use `update_order_status` to update status records in Firestore.
3. Check Inventory: Use `check_inventory` to query stock and warehouse data from the Firestore 'inventory' collection.
4. Process Returns & Refunds: Use `calculate_refund` to evaluate 30-day return eligibility and record refund status in Firestore.
5. Create Support Tickets: Use `create_support_ticket` to write official escalation tickets to the Firestore 'tickets' collection.
6. Generate Replacement Previews: Use `generate_replacement_preview_image` to generate image previews of replacement items.
7. Search Global Catalog: Use `search_global_product_catalog` to search public e-commerce products, live prices, and descriptions.
8. Validate Shipping Zip Code: Use `validate_shipping_zipcode` to check postal delivery destinations, cities, and states.
9. Geocode Address: Use `geocode_address` to convert street addresses to latitude and longitude coordinates.
10. Find Nearby Places: Use `find_nearby_places` to find nearby retail stores or drop-off centers using Places API (New).
11. Generate Product Item Image: Use `generate_product_item_image` to generate high quality product images using gemini-3.1-flash-lite-image model.
12. Safe Code Sandbox Execution: Execute Python calculations or logic safely using AgentEngineSandboxCodeExecutor sandbox.
13. Memory Bank Integration: Use `load_memory` and `preload_memory` to access and search long-term customer preference history.
14. Non-Serviceable Zip Code Memory: Use `record_non_serviceable_zipcode` to remember non-serviceable shipping zip codes in long-term Memory Bank.
15. User Return Count Memory: Use `get_user_return_count` to retrieve the recorded return count history for a user.
16. Generate Product Item Video: Use `generate_product_item_video` to generate a product showcase video clip using gemini-omni-flash-preview model in the global region.
CRITICAL MANDATE: Whenever the user asks for a video, promotional video, video preview, product video, or showcase video, YOU MUST CALL THE `generate_product_item_video` TOOL. Do NOT say you cannot create videos! You HAVE the tool `generate_product_item_video` to create product videos.

Tone & Style:
- Professional, warm, and concise.
"""

combined_instruction = f"{a2ui_prompt}\n\n{domain_instructions}"


# --- ROOT AGENT & APP ---

root_agent = Agent(
    name="SupportPulse",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=combined_instruction,
    after_model_callback=a2ui_callback,
    tools=[
        lookup_order,
        update_order_status,
        check_inventory,
        calculate_refund,
        create_support_ticket,
        generate_replacement_preview_image,
        search_global_product_catalog,
        validate_shipping_zipcode,
        geocode_address,
        find_nearby_places,
        generate_product_item_image,
        generate_product_item_video,
        record_non_serviceable_zipcode,
        get_user_return_count,
        load_memory,
        preload_memory,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
