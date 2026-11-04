import sys
import datetime
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import (
    QTableWidgetItem, QMessageBox, QInputDialog, QDialog, QVBoxLayout, 
    QTextEdit, QPushButton, QComboBox, QLineEdit, QDoubleSpinBox, 
    QDialogButtonBox, QLabel, QHBoxLayout, QSpinBox
)
from CatalogManager import populate_catalog_view, load_catalog_dict, ITEM_TYPES, CATEGORY_ALL


def trim_empty_margins(image):
    """Crops transparent / white borders around a logo so the artwork fills the space it is given."""
    image = image.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    small = image.scaled(256, 256, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                         QtCore.Qt.TransformationMode.SmoothTransformation)
    left, top, right, bottom = small.width(), small.height(), -1, -1
    for y in range(small.height()):
        for x in range(small.width()):
            c = small.pixelColor(x, y)
            if c.alpha() > 20 and not (c.red() > 245 and c.green() > 245 and c.blue() > 245):
                left, right = min(left, x), max(right, x)
                top, bottom = min(top, y), max(bottom, y)
    if right < 0:
        return image
    scale_x = image.width() / small.width()
    scale_y = image.height() / small.height()
    rect = QtCore.QRect(
        int(left * scale_x), int(top * scale_y),
        int((right - left + 1) * scale_x), int((bottom - top + 1) * scale_y)
    ).adjusted(-2, -2, 2, 2).intersected(image.rect())
    return image.copy(rect)


def apply_app_font(app):
    """Sets a larger, narrower (condensed) default font for the whole app.
    The first installed family in the list is used; setStretch narrows it further
    when the family supports it."""
    font = QtGui.QFont()
    font.setFamilies([
        "Segoe UI Semilight", "Roboto Condensed", "Arial Narrow",
        "DejaVu Sans Condensed", "Helvetica Neue", "Segoe UI", "Arial",
    ])
    font.setPointSize(20)                
    font.setStretch(70)                  
    font.setHintingPreference(QtGui.QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)


class DiscountDialog(QDialog):
    """Dialog requiring Discount Type, Customer Name, and ID/Promo Code Number."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Apply Discount")
        self.resize(540, 420)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 1. Discount Type Selection
        layout.addWidget(QLabel("<b>1. Select Discount Type:</b>"))
        self.typeCombo = QComboBox(self)
        self.typeCombo.addItems([
            "Senior Citizen / PWD (20%)",
            "Coupon / Promo Discount"
        ])
        layout.addWidget(self.typeCombo)

        # 2. Name Input (Mandatory)
        layout.addWidget(QLabel("<b>2. Customer / Holder Name:</b>"))
        self.nameInput = QLineEdit(self)
        self.nameInput.setPlaceholderText("Enter full name (e.g. Juan Dela Cruz)")
        layout.addWidget(self.nameInput)

        # 3. ID / Code Input (Mandatory)
        layout.addWidget(QLabel("<b>3. ID / Promo Code Number:</b>"))
        self.idInput = QLineEdit(self)
        self.idInput.setPlaceholderText("Enter OSCA/PWD ID or Promo Code #")
        layout.addWidget(self.idInput)

        # 4. Custom Percentage (Visible only for Coupon/Promo)
        self.percentLabel = QLabel("<b>4. Discount Percentage (%):</b>")
        self.percentInput = QDoubleSpinBox(self)
        self.percentInput.setRange(0.1, 100.0)
        self.percentInput.setValue(10.0)
        self.percentInput.setSuffix("%")
        
        layout.addWidget(self.percentLabel)
        layout.addWidget(self.percentInput)

        # Connect Type Toggle
        self.typeCombo.currentIndexChanged.connect(self.on_type_changed)
        self.on_type_changed(0)  # Default: Senior/PWD

        # OK / Cancel Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self
        )
        btn_box.accepted.connect(self.validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def on_type_changed(self, index):
        if index == 0:  # Senior / PWD
            self.percentLabel.setVisible(False)
            self.percentInput.setVisible(False)
        else:  # Coupon / Promo
            self.percentLabel.setVisible(True)
            self.percentInput.setVisible(True)

    def validate_and_accept(self):
        if not self.nameInput.text().strip():
            QMessageBox.warning(self, "Input Required", "Customer / Holder Name is required.")
            self.nameInput.setFocus()
            return
        if not self.idInput.text().strip():
            QMessageBox.warning(self, "Input Required", "ID Number or Promo Code Number is required.")
            self.idInput.setFocus()
            return
        self.accept()

    def get_data(self):
        is_senior = (self.typeCombo.currentIndex() == 0)
        discount_type = "Senior/PWD" if is_senior else "Coupon/Promo"
        percent = 20.0 if is_senior else self.percentInput.value()
        return {
            "type": discount_type,
            "name": self.nameInput.text().strip(),
            "id": self.idInput.text().strip(),
            "percent": percent
        }


class RemoveItemDialog(QDialog):
    """Asks how many units to remove and confirms with Yes/No."""
    def __init__(self, item_name, current_qty, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remove Item")
        self.setMinimumWidth(360)
        self.current_qty = current_qty

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel(f"<b>{item_name}</b><br>Quantity in cart: {current_qty}"))

        # Quantity chooser
        layout.addWidget(QLabel("<b>Quantity to remove:</b>"))
        qty_row = QHBoxLayout()
        self.qtySpin = QSpinBox(self)
        self.qtySpin.setRange(1, current_qty)
        self.qtySpin.setValue(1)
        self.removeAllBtn = QPushButton("Remove All", self)
        self.removeAllBtn.clicked.connect(lambda: self.qtySpin.setValue(self.current_qty))
        qty_row.addWidget(self.qtySpin, 1)
        qty_row.addWidget(self.removeAllBtn)
        layout.addLayout(qty_row)

        layout.addWidget(QLabel("<b>Are you sure you want to remove this item?</b>"))

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No, self
        )
        btn_box.button(QDialogButtonBox.StandardButton.No).setDefault(True)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_quantity(self):
        return self.qtySpin.value()


class ReceiptDialog(QDialog):
    """Modal dialog displaying the transaction receipt immediately after payment."""
    def __init__(self, receipt_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Official Receipt")
        self.resize(600, 720)
        
        layout = QVBoxLayout(self)

        # Store logo at the top of the receipt
        self.logoLabel = QLabel(self)
        self.logoLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        try:
            dpr = QtWidgets.QApplication.primaryScreen().devicePixelRatio()
            logo = QtGui.QPixmap.fromImage(trim_empty_margins(QtGui.QImage("ARK.png")))
            logo = logo.scaledToHeight(int(90 * dpr), QtCore.Qt.TransformationMode.SmoothTransformation)
            logo.setDevicePixelRatio(dpr)
            self.logoLabel.setPixmap(logo)
        except Exception:
            self.logoLabel.hide()
        layout.addWidget(self.logoLabel)

        self.textEdit = QTextEdit(self)
        self.textEdit.setReadOnly(True)
        self.textEdit.setFont(QtGui.QFont("Courier New", 14))
        self.textEdit.setText(receipt_text)
        layout.addWidget(self.textEdit)

        self.closeBtn = QPushButton("Close & Start New Transaction", self)
        self.closeBtn.setMinimumHeight(40)
        self.closeBtn.clicked.connect(self.accept)
        layout.addWidget(self.closeBtn)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        self.MainWindow = MainWindow
        MainWindow.setWindowTitle("ARK Supermarket Cash Register")
        MainWindow.setWindowIcon(QtGui.QIcon("ARK.png"))
        MainWindow.resize(1280, 820)
        MainWindow.setMinimumSize(1000, 700)

        self.csv_filepath = "catalog.csv"
        self.catalog_db = load_catalog_dict(self.csv_filepath)
        self.current_category = CATEGORY_ALL

        # Discount Tracker State
        self.applied_discount = 0.0  # Fraction (e.g. 0.20)
        self.discount_type_label = ""
        self.discount_name = ""
        self.discount_id = ""

        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)

        # Action Buttons
        self.removeB = QtWidgets.QPushButton("REMOVE (Double-Click)", parent=self.centralwidget)
        self.discountB = QtWidgets.QPushButton("DISCOUNT", parent=self.centralwidget)
        self.paymentB = QtWidgets.QPushButton("PAYMENT", parent=self.centralwidget)

        for btn in (self.removeB, self.discountB, self.paymentB):
            btn.setMinimumHeight(60)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        self.removeB.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; font-size: 21px;")
        self.discountB.setStyleSheet("background-color: #f0ad4e; color: white; font-weight: bold; font-size: 21px;")
        self.paymentB.setStyleSheet("background-color: #5cb85c; color: white; font-weight: bold; font-size: 21px;")

        # Cart Table Initialization
        self.itemList = QtWidgets.QTableWidget(parent=self.centralwidget)
        self.itemList.setColumnCount(5)
        self.itemList.setHorizontalHeaderLabels(["SN", "Item Name", "Price", "Qty", "Total"])
        self.itemList.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.itemList.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.itemList.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.itemList.verticalHeader().setDefaultSectionSize(46)
        self.itemList.verticalHeader().setVisible(False)
        self.itemList.horizontalHeader().setStyleSheet("QHeaderView::section { font-weight: bold; font-size: 19px; padding: 6px; }")
        self.itemList.setStyleSheet("QTableWidget { font-size: 20px; }")

        # Catalog List View
        self.itemCatalog = QtWidgets.QListView(parent=self.centralwidget)
        self.itemCatalog.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        self.itemCatalog.setViewMode(QtWidgets.QListView.ViewMode.IconMode)

        # Totals Labels
        self.totalnet = QtWidgets.QLabel("Net Total: ₱0.00", parent=self.centralwidget)

        for label in (self.totalnet,):
            label.setStyleSheet("font-size: 23px; font-weight: bold;")

        # Live Discount UI Status Label
        self.discountLabel = QtWidgets.QLabel("Applied Discount: None", parent=self.centralwidget)
        self.discountLabel.setStyleSheet("font-size: 18px; font-weight: bold; color: #6c757d; padding: 4px;")

        # Search Bar & Serial Punch Input
        self.searchItem = QtWidgets.QLineEdit(parent=self.centralwidget)
        self.searchItem.setPlaceholderText("🔍 Search Catalog (Name / SN)")

        self.enterItem = QtWidgets.QLineEdit(parent=self.centralwidget)
        self.enterItem.setPlaceholderText("Enter Serial Number and press Enter to punch item")
        for box in (self.searchItem, self.enterItem):
            box.setMinimumHeight(46)
            box.setStyleSheet("font-size: 20px;")
        self.itemCatalog.setStyleSheet("QListView { font-size: 18px; }")

        # Category Filter Grid
        self.categoryGrid = QtWidgets.QGridLayout()
        self.categoryGrid.setSpacing(8)
        self.categoryGroup = QtWidgets.QButtonGroup(self.centralwidget)
        self.categoryGroup.setExclusive(True)
        self.category_buttons = {}

        categories = [CATEGORY_ALL] + list(ITEM_TYPES.values())
        columns = 4
        for index, category in enumerate(categories):
            btn = QtWidgets.QPushButton(category, parent=self.centralwidget)
            btn.setCheckable(True)
            btn.setMinimumHeight(52)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(
                "QPushButton { font-size: 19px; } "
                "QPushButton:checked { background-color: #2d89ef; color: white; font-weight: bold; }"
            )
            btn.clicked.connect(lambda checked, c=category: self.filter_category(c))
            self.categoryGroup.addButton(btn)
            self.category_buttons[category] = btn
            self.categoryGrid.addWidget(btn, index // columns, index % columns)

        self.category_buttons[CATEGORY_ALL].setChecked(True)

        # Layout Assembly
        totals_row = QtWidgets.QHBoxLayout()
        totals_row.addWidget(self.totalnet)

        buttons_row = QtWidgets.QHBoxLayout()
        buttons_row.setSpacing(15)
        buttons_row.addWidget(self.removeB)
        buttons_row.addWidget(self.discountB)
        buttons_row.addWidget(self.paymentB)

        left_col = QtWidgets.QVBoxLayout()
        header_height = 80
        self.logoLabel = QtWidgets.QLabel(parent=self.centralwidget)
        
        # Scale logo smoothly
        try:
            dpr = QtWidgets.QApplication.primaryScreen().devicePixelRatio()
            logo = QtGui.QPixmap.fromImage(trim_empty_margins(QtGui.QImage("ARK.png")))
            logo = logo.scaledToHeight(int(header_height * dpr), QtCore.Qt.TransformationMode.SmoothTransformation)
            logo.setDevicePixelRatio(dpr)
            self.logoLabel.setPixmap(logo)
        except Exception:
            pass

        left_header = QtWidgets.QHBoxLayout()
        left_header.setSpacing(15)
        left_header.addWidget(self.logoLabel)
        left_header.addWidget(QtWidgets.QLabel("<b style='font-size:24px;'>CART / TRANSACTION ITEMS</b>"))
        left_header.addStretch(1)

        left_col.addLayout(left_header)
        left_col.addWidget(self.itemList, 1)
        left_col.addWidget(self.discountLabel)  # <-- Live Discount Reflection Banner
        left_col.addLayout(totals_row)
        left_col.addLayout(buttons_row)
        left_col.addWidget(self.enterItem)

        right_col = QtWidgets.QVBoxLayout()
        catalog_title = QtWidgets.QLabel("<b style='font-size:24px;'>PRODUCT CATALOG</b>")
        catalog_title.setFixedHeight(header_height)
        right_col.addWidget(catalog_title)
        right_col.addWidget(self.searchItem)
        right_col.addWidget(self.itemCatalog, 1)
        right_col.addLayout(self.categoryGrid)

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.setSpacing(35)
        main_layout.addLayout(left_col, 11)
        main_layout.addLayout(right_col, 10)

        main_layout.setContentsMargins(25, 10, 25, 20)
        self.centralwidget.setLayout(main_layout)

        MainWindow.setCentralWidget(self.centralwidget)

        # Menu Bar
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.actionExit = QtGui.QAction("Exit", MainWindow)
        self.actionExit.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        self.actionExit.triggered.connect(MainWindow.close)
        self.menubar.addAction(self.actionExit)
        MainWindow.setMenuBar(self.menubar)

        self.statusbar = QtWidgets.QStatusBar(parent=MainWindow)
        MainWindow.setStatusBar(self.statusbar)

        # Load Initial Catalog View
        populate_catalog_view(self.csv_filepath, self.itemCatalog, CATEGORY_ALL)

        # Connect Event Signals
        self.itemCatalog.doubleClicked.connect(self.on_catalog_item_double_clicked)
        self.itemCatalog.clicked.connect(self.on_catalog_item_clicked)
        self.itemList.itemDoubleClicked.connect(self.remove_item_double_clicked)
        self.enterItem.returnPressed.connect(self.punch_item_by_sn)
        self.searchItem.textChanged.connect(self.on_search_changed)
        self.removeB.clicked.connect(self.remove_selected_cart_item)
        self.discountB.clicked.connect(self.apply_discount)
        self.paymentB.clicked.connect(self.process_payment)

    # --- COMPUTATION & ITEM PUNCHING ---
    def add_to_cart(self, sn, name, price):
        for row in range(self.itemList.rowCount()):
            if self.itemList.item(row, 0).text() == sn:
                current_qty = int(self.itemList.item(row, 3).text())
                new_qty = current_qty + 1
                new_total = new_qty * price

                self.itemList.item(row, 3).setText(str(new_qty))
                self.itemList.item(row, 4).setText(f"₱{new_total:,.2f}")
                self.calculate_totals()
                return

        row_pos = self.itemList.rowCount()
        self.itemList.insertRow(row_pos)

        item_sn = QTableWidgetItem(sn)
        item_name = QTableWidgetItem(name)
        item_price = QTableWidgetItem(f"₱{price:,.2f}")
        item_qty = QTableWidgetItem("1")
        item_total = QTableWidgetItem(f"₱{price:,.2f}")

        item_sn.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        item_price.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        item_qty.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        item_total.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.itemList.setItem(row_pos, 0, item_sn)
        self.itemList.setItem(row_pos, 1, item_name)
        self.itemList.setItem(row_pos, 2, item_price)
        self.itemList.setItem(row_pos, 3, item_qty)
        self.itemList.setItem(row_pos, 4, item_total)

        self.calculate_totals()

    def on_catalog_item_double_clicked(self, index):
        self.punch_catalog_index(index)

    def on_catalog_item_clicked(self, index):
        self.punch_catalog_index(index)

    def punch_catalog_index(self, index):
        sn = index.data(QtCore.Qt.ItemDataRole.UserRole)
        price = index.data(QtCore.Qt.ItemDataRole.UserRole + 2)
        name = index.data(QtCore.Qt.ItemDataRole.UserRole + 3)

        if sn and name and price is not None:
            self.add_to_cart(sn, name, float(price))

    def punch_item_by_sn(self):
        sn = self.enterItem.text().strip()
        if not sn:
            return

        if sn in self.catalog_db:
            item = self.catalog_db[sn]
            self.add_to_cart(item["sn"], item["name"], item["price"])
            self.enterItem.clear()
        else:
            QMessageBox.warning(self.MainWindow, "Item Not Found", f"No item found with Serial Number: {sn}")

    # --- DELETE FUNCTION ---
    def remove_item_double_clicked(self, item):
        self.remove_cart_row(item.row())

    def remove_selected_cart_item(self):
        current_row = self.itemList.currentRow()
        if current_row >= 0:
            self.remove_cart_row(current_row)
        else:
            QMessageBox.information(self.MainWindow, "Selection Required", "Please select an item in the cart to remove.")

    def remove_cart_row(self, row):
        """Remove a chosen quantity of the item in `row`, after Yes/No confirmation."""
        name = self.itemList.item(row, 1).text()
        current_qty = int(self.itemList.item(row, 3).text())

        dialog = RemoveItemDialog(name, current_qty, self.MainWindow)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        remove_qty = dialog.get_quantity()
        new_qty = current_qty - remove_qty

        if new_qty <= 0:
            self.itemList.removeRow(row)
        else:
            price = float(self.itemList.item(row, 2).text().replace("₱", "").replace(",", "").strip())
            self.itemList.item(row, 3).setText(str(new_qty))
            self.itemList.item(row, 4).setText(f"₱{new_qty * price:,.2f}")

        # Don't carry a discount over to an empty cart
        if self.itemList.rowCount() == 0:
            self.applied_discount = 0.0
            self.discount_type_label = ""
            self.discount_name = ""
            self.discount_id = ""

        self.calculate_totals()
        self.statusbar.showMessage(f"Removed {remove_qty} x {name}", 4000)

    # --- SEARCH & FILTERING ---
    def on_search_changed(self, text):
        populate_catalog_view(self.csv_filepath, self.itemCatalog, self.current_category, text)

    def filter_category(self, category):
        self.current_category = category
        search_text = self.searchItem.text()
        populate_catalog_view(self.csv_filepath, self.itemCatalog, category, search_text)

    # --- TOTALS COMPUTATION & UI REFLECTION ---
    def calculate_totals(self):
        total_amount = 0.0
        for row in range(self.itemList.rowCount()):
            total_str = self.itemList.item(row, 4).text().replace("₱", "").replace(",", "").strip()
            total_amount += float(total_str)

        discount_amount = total_amount * self.applied_discount
        final_total = total_amount - discount_amount

        # VAT calculations
        vatable_sales = final_total / 1.12
        vat_amount = final_total - vatable_sales

        self.totalnet.setText(f"Net Total: ₱{final_total:,.2f}")

        # Update Live Discount UI Banner
        if self.applied_discount > 0:
            self.discountLabel.setText(
                f"🏷️ <b>Applied Discount ({self.discount_type_label}):</b> {self.applied_discount * 100:.1f}% (-₱{discount_amount:,.2f})<br>"
                f"👤 <b>Holder:</b> {self.discount_name} &nbsp;|&nbsp; 🆔 <b>ID/Code #:</b> {self.discount_id}"
            )
            self.discountLabel.setStyleSheet(
                "font-size: 18px; font-weight: normal; color: #155724; "
                "background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 4px; padding: 6px;"
            )
        else:
            self.discountLabel.setText("Applied Discount: None")
            self.discountLabel.setStyleSheet("font-size: 18px; font-weight: bold; color: #6c757d; padding: 4px;")

        return vatable_sales, vat_amount, final_total, discount_amount

    # --- DISCOUNT HANDLING WITH DIALOG ---
    def apply_discount(self):
        if self.itemList.rowCount() == 0:
            QMessageBox.information(self.MainWindow, "Empty Cart", "Add items to cart before applying discount.")
            return

        dialog = DiscountDialog(self.MainWindow)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.discount_type_label = data["type"]
            self.discount_name = data["name"]
            self.discount_id = data["id"]
            self.applied_discount = data["percent"] / 100.0

            self.calculate_totals()
            QMessageBox.information(
                self.MainWindow, 
                "Discount Applied", 
                f"{data['percent']}% {data['type']} discount successfully applied for {data['name']}!"
            )

    # --- PAYMENT & IMMEDIATE RECEIPT ---
    def process_payment(self):
        if self.itemList.rowCount() == 0:
            QMessageBox.warning(self.MainWindow, "Empty Cart", "Cannot process payment with an empty cart!")
            return

        vatable_sales, vat_amount, grand_total, discount_amount = self.calculate_totals()

        payment_amount, ok = QInputDialog.getDouble(
            self.MainWindow, "Payment Processing", f"Grand Total Due: ₱{grand_total:,.2f}\nEnter Payment Amount:", grand_total, 0, 100000, 2
        )

        if not ok:
            return

        if payment_amount < grand_total:
            QMessageBox.critical(self.MainWindow, "Insufficient Payment", f"Payment amount (₱{payment_amount:,.2f}) is less than Total Due (₱{grand_total:,.2f}).")
            return

        change = payment_amount - grand_total

        # Generate Receipt Text
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        receipt_text = f"{'ARK SUPERMARKET':^40}\n"
        receipt_text += f"{'123 P. Tuazon Blvd., Cubao':^40}\n"
        receipt_text += f"{'Quezon City, Metro Manila':^40}\n"
        receipt_text += f"{'========================================':^40}\n"
        receipt_text += f"Date/Time: {now}\n"
        receipt_text += f"{'----------------------------------------':^40}\n"
        receipt_text += f"{'Item':<20} {'Qty':<4} {'Price':<7} {'Total':<7}\n"
        receipt_text += f"{'----------------------------------------':^40}\n"

        for row in range(self.itemList.rowCount()):
            name = self.itemList.item(row, 1).text()
            if len(name) > 19:
                name = name[:16] + "..."
            qty = self.itemList.item(row, 3).text()
            price = self.itemList.item(row, 2).text().replace("₱", "").strip()
            total = self.itemList.item(row, 4).text().replace("₱", "").strip()
            receipt_text += f"{name:<20} {qty:<4} {price:<7} {total:<7}\n"

        receipt_text += f"{'----------------------------------------':^40}\n"
        receipt_text += f"{'VATable Sales:':<25} ₱{vatable_sales:>10,.2f}\n"
        receipt_text += f"{'12% VAT:':<25} ₱{vat_amount:>10,.2f}\n"
        
        if discount_amount > 0:
            receipt_text += f"{'Discount Type:':<25} {self.discount_type_label}\n"
            receipt_text += f"{'Holder Name:':<25} {self.discount_name}\n"
            receipt_text += f"{'ID/Code #:':<25} {self.discount_id}\n"
            receipt_text += f"{'Discount Saved:':<25} -₱{discount_amount:>10,.2f}\n"

        receipt_text += f"{'GRAND TOTAL:':<25} ₱{grand_total:>10,.2f}\n"
        receipt_text += f"{'Payment Amount:':<25} ₱{payment_amount:>10,.2f}\n"
        receipt_text += f"{'Change:':<25} ₱{change:>10,.2f}\n"
        receipt_text += f"{'========================================':^40}\n"
        receipt_text += f"{'THANK YOU FOR SHOPPING AT ARK!':^40}\n"

        # Show Receipt Dialog Immediately
        dialog = ReceiptDialog(receipt_text, self.MainWindow)
        dialog.exec()

        # Clear Cart & Reset Discount State for Next Transaction
        self.itemList.setRowCount(0)
        self.applied_discount = 0.0
        self.discount_type_label = ""
        self.discount_name = ""
        self.discount_id = ""
        self.calculate_totals()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    apply_app_font(app)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())