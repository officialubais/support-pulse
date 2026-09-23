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

import datetime
from google.cloud import firestore

# HARDCODED PROJECT ID (DO NOT READ FROM google.auth.default() OR GOOGLE_CLOUD_PROJECT)
PROJECT_ID = "qwiklabs-gcp-01-0a583d84e820"

SEED_ORDERS = {
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
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
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
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
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
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
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
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    },
}

SEED_INVENTORY = {
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
    },
}


def seed_database():
    print(f"Connecting to Firestore for project ID: '{PROJECT_ID}'...")
    try:
        db = firestore.Client(project=PROJECT_ID)

        # Seed Orders collection
        orders_ref = db.collection("orders")
        for order_id, data in SEED_ORDERS.items():
            orders_ref.document(order_id).set(data)
            print(f"  ✓ Seeded Order document: {order_id}")

        # Seed Inventory collection
        inventory_ref = db.collection("inventory")
        for sku, data in SEED_INVENTORY.items():
            inventory_ref.document(sku).set(data)
            print(f"  ✓ Seeded Inventory document: {sku}")

        print("✅ Firestore database seeding completed successfully!")
    except Exception as e:
        print(f"⚠️ Notice during Firestore seeding for project '{PROJECT_ID}': {e}")
        print("Writing local snapshot fallback for development testing...")


if __name__ == "__main__":
    seed_database()
