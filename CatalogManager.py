import csv
import os
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QStandardItemModel, QStandardItem

CATEGORY_ALL = "All"

ITEM_TYPES = {
    "10": "Fruit",
    "20": "Vegetable",
    "30": "Drink",
    "40": "Meat",
    "50": "Dairy",
    "60": "Laundry",
    "70": "Bread",
    "80": "Appliances",
    "90": "Stationery"
}


def load_catalog_dict(filepath):
    """Loads CSV data into a dictionary indexed by Serial Number for fast lookup."""
    catalog = {}
    if not os.path.exists(filepath):
        return catalog

    try:
        with open(filepath, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader, None)  # Skip header
            for row in reader:
                if len(row) >= 4:
                    item_name = row[0].strip()
                    sn = row[1].strip()
                    img = row[2].strip()
                    price_text = row[3].strip()

                    try:
                        price = float(price_text)
                    except ValueError:
                        price = 0.0

                    type_code = sn[:2]
                    category = ITEM_TYPES.get(type_code, "Other")

                    catalog[sn] = {
                        "name": item_name,
                        "sn": sn,
                        "image": img,
                        "price": price,
                        "category": category
                    }
    except Exception as e:
        print(f"Error loading catalog dictionary: {e}")

    return catalog


def populate_catalog_view(filepath, list_view, category_filter=CATEGORY_ALL, search_query=""):
    """Reads CSV and populates QListView with optional category and search filtering."""
    model = QStandardItemModel()

    try:
        with open(filepath, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader, None)  # Skip header

            for row in reader:
                if len(row) >= 4:
                    item_name = row[0].strip()
                    serial_number = row[1].strip()
                    image_path = row[2].strip()
                    price_text = row[3].strip()

                    try:
                        price = float(price_text)
                    except ValueError:
                        price = 0.0

                    type_code = serial_number[:2]
                    category = ITEM_TYPES.get(type_code, "Other")

                    # Category Filter
                    if category_filter != CATEGORY_ALL and category != category_filter:
                        continue

                    # Search Filter
                    if search_query:
                        query = search_query.lower()
                        if query not in item_name.lower() and query not in serial_number.lower():
                            continue

                    display_text = f"[{category}] {item_name}\nSN: {serial_number} | ₱{price:,.2f}"
                    catalog_item = QStandardItem(display_text)

                    if image_path and os.path.exists(image_path):
                        catalog_item.setIcon(QtGui.QIcon(image_path))

                    # Store metadata directly inside UserRoles
                    catalog_item.setData(serial_number, QtCore.Qt.ItemDataRole.UserRole)
                    catalog_item.setData(category, QtCore.Qt.ItemDataRole.UserRole + 1)
                    catalog_item.setData(price, QtCore.Qt.ItemDataRole.UserRole + 2)
                    catalog_item.setData(item_name, QtCore.Qt.ItemDataRole.UserRole + 3)

                    catalog_item.setEditable(False)
                    model.appendRow(catalog_item)

        list_view.setModel(model)
        list_view.setIconSize(QtCore.QSize(80, 80))
        list_view.setWordWrap(True)
        list_view.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        list_view.setSpacing(15)
        list_view.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        list_view.setMovement(QtWidgets.QListView.Movement.Static)

    except FileNotFoundError:
        print(f"Error: The file {filepath} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")