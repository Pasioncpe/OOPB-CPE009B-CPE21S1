import sys
import datetime
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QTableWidgetItem, QMessageBox, QInputDialog, QDialog, QVBoxLayout, QTextEdit, QPushButton
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


# A module to print the receipt immediately after payment in another window
class ReceiptDialog(QDialog):
    """Modal dialog displaying the transaction receipt immediately after payment."""
    def __init__(self, receipt_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Official Receipt")
        self.resize(420, 560)
        
        layout = QVBoxLayout(self)

        self.textEdit = QTextEdit(self)
        self.textEdit.setReadOnly(True)
        self.textEdit.setFont(QtGui.QFont("Courier New", 10))
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
        MainWindow.resize(1150, 780)
        MainWindow.setMinimumSize(900, 650)

        self.csv_filepath = "catalog.csv"
        self.catalog_db = load_catalog_dict(self.csv_filepath)
        self.current_category = CATEGORY_ALL
        self.applied_discount = 0.0  # Percentage discount (e.g., 0.20 for 20%)

        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)

        # Action Buttons
        self.removeB = QtWidgets.QPushButton("REMOVE (Double-Click)", parent=self.centralwidget)
        self.discountB = QtWidgets.QPushButton("DISCOUNT", parent=self.centralwidget)
        self.paymentB = QtWidgets.QPushButton("PAYMENT", parent=self.centralwidget)

        for btn in (self.removeB, self.discountB, self.paymentB):
            btn.setMinimumHeight(45)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        self.removeB.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; font-size: 13px;")
        self.discountB.setStyleSheet("background-color: #f0ad4e; color: white; font-weight: bold; font-size: 13px;")
        self.paymentB.setStyleSheet("background-color: #5cb85c; color: white; font-weight: bold; font-size: 13px;")

        # Cart Table Initialization
        self.itemList = QtWidgets.QTableWidget(parent=self.centralwidget)
        self.itemList.setColumnCount(5)
        self.itemList.setHorizontalHeaderLabels(["SN", "Item Name", "Price", "Qty", "Total"])
        self.itemList.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.itemList.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.itemList.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        # Catalog List View
        self.itemCatalog = QtWidgets.QListView(parent=self.centralwidget)
        self.itemCatalog.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        self.itemCatalog.setViewMode(QtWidgets.QListView.ViewMode.IconMode)

        # Totals Labels
        self.totalsub = QtWidgets.QLabel("Subtotal: ₱0.00", parent=self.centralwidget)
        self.totalvat = QtWidgets.QLabel("12% VAT: ₱0.00", parent=self.centralwidget)
        self.totalgrand = QtWidgets.QLabel("Grand Total: ₱0.00", parent=self.centralwidget)

        for label in (self.totalsub, self.totalvat, self.totalgrand):
            label.setStyleSheet("font-size: 14px; font-weight: bold;")

        # Search Bar & Serial Punch Input
        self.searchItem = QtWidgets.QLineEdit(parent=self.centralwidget)
        self.searchItem.setPlaceholderText("🔍 Search Catalog (Name / SN)")

        self.enterItem = QtWidgets.QLineEdit(parent=self.centralwidget)
        self.enterItem.setPlaceholderText("Enter Serial Number and press Enter to punch item")

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
            btn.setMinimumHeight(38)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(
                "QPushButton:checked { background-color: #2d89ef; color: white; font-weight: bold; }"
            )
            btn.clicked.connect(lambda checked, c=category: self.filter_category(c))
            self.categoryGroup.addButton(btn)
            self.category_buttons[category] = btn
            self.categoryGrid.addWidget(btn, index // columns, index % columns)

        self.category_buttons[CATEGORY_ALL].setChecked(True)

        # Layout Assembly
        totals_row = QtWidgets.QHBoxLayout()
        totals_row.addWidget(self.totalsub)
        totals_row.addWidget(self.totalvat)
        totals_row.addWidget(self.totalgrand)

        buttons_row = QtWidgets.QHBoxLayout()
        buttons_row.setSpacing(15)
        buttons_row.addWidget(self.removeB)
        buttons_row.addWidget(self.discountB)
        buttons_row.addWidget(self.paymentB)

        left_col = QtWidgets.QVBoxLayout()
        header_height = 70
        self.logoLabel = QtWidgets.QLabel(parent=self.centralwidget)
        # Scale to the screen's real pixel density so the logo stays sharp on scaled displays
        dpr = QtWidgets.QApplication.primaryScreen().devicePixelRatio()
        logo = QtGui.QPixmap.fromImage(trim_empty_margins(QtGui.QImage("ARK.png")))
        logo = logo.scaledToHeight(int(header_height * dpr), QtCore.Qt.TransformationMode.SmoothTransformation)
        logo.setDevicePixelRatio(dpr)
        self.logoLabel.setPixmap(logo)

        left_header = QtWidgets.QHBoxLayout()
        left_header.setSpacing(15)
        left_header.addWidget(self.logoLabel)
        left_header.addWidget(QtWidgets.QLabel("<b>CART / TRANSACTION ITEMS</b>"))
        left_header.addStretch(1)
        left_col.addLayout(left_header)
        left_col.addWidget(self.itemList, 1)
        left_col.addLayout(totals_row)
        left_col.addLayout(buttons_row)
        left_col.addWidget(self.enterItem)

        right_col = QtWidgets.QVBoxLayout()
        catalog_title = QtWidgets.QLabel("<b>PRODUCT CATALOG</b>")
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

    # - COMPUTATION & ITEM PUNCHING -----
    def add_to_cart(self, sn, name, price):
        """Adds an item to the QTableWidget cart or increments quantity if already exists."""
        for row in range(self.itemList.rowCount()):
            if self.itemList.item(row, 0).text() == sn:
                current_qty = int(self.itemList.item(row, 3).text())
                new_qty = current_qty + 1
                new_total = new_qty * price

                self.itemList.item(row, 3).setText(str(new_qty))
                self.itemList.item(row, 4).setText(f"₱{new_total:,.2f}")
                self.calculate_totals()
                return

        # Add new row if item is not in cart
        row_pos = self.itemList.rowCount()
        self.itemList.insertRow(row_pos)

        item_sn = QTableWidgetItem(sn)
        item_name = QTableWidgetItem(name)
        item_price = QTableWidgetItem(f"₱{price:,.2f}")
        item_qty = QTableWidgetItem("1")
        item_total = QTableWidgetItem(f"₱{price:,.2f}")

        # Align text nicely
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
        """Punches item to cart when double-clicked in catalog."""
        self.punch_catalog_index(index)

    def on_catalog_item_clicked(self, index):
        """Punches item to cart when clicked in catalog."""
        self.punch_catalog_index(index)

    def punch_catalog_index(self, index):
        sn = index.data(QtCore.Qt.ItemDataRole.UserRole)
        price = index.data(QtCore.Qt.ItemDataRole.UserRole + 2)
        name = index.data(QtCore.Qt.ItemDataRole.UserRole + 3)

        if sn and name and price is not None:
            self.add_to_cart(sn, name, float(price))

    def punch_item_by_sn(self):
        """Punches item when serial number is entered into input box."""
        sn = self.enterItem.text().strip()
        if not sn:
            return

        if sn in self.catalog_db:
            item = self.catalog_db[sn]
            self.add_to_cart(item["sn"], item["name"], item["price"])
            self.enterItem.clear()
        else:
            QMessageBox.warning(self.MainWindow, "Item Not Found", f"No item found with Serial Number: {sn}")

    # --- DELETE FUNCTION (DOUBLE-CLICK & BUTTON) ---
    def remove_item_double_clicked(self, item):
        """Removes row on double-click from cart QTableWidget."""
        row = item.row()
        self.itemList.removeRow(row)
        self.calculate_totals()

    def remove_selected_cart_item(self):
        """Removes currently selected row in cart QTableWidget."""
        current_row = self.itemList.currentRow()
        if current_row >= 0:
            self.itemList.removeRow(current_row)
            self.calculate_totals()
        else:
            QMessageBox.information(self.MainWindow, "Selection Required", "Please select an item in the cart to remove.")

    # --- SEARCH & FILTERING ---
    def on_search_changed(self, text):
        populate_catalog_view(self.csv_filepath, self.itemCatalog, self.current_category, text)

    def filter_category(self, category):
        self.current_category = category
        search_text = self.searchItem.text()
        populate_catalog_view(self.csv_filepath, self.itemCatalog, category, search_text)

    # --- TOTALS COMPUTATION ---
    def calculate_totals(self):
        total_amount = 0.0
        for row in range(self.itemList.rowCount()):
            total_str = self.itemList.item(row, 4).text().replace("₱", "").replace(",", "").strip()
            total_amount += float(total_str)

        discount_amount = total_amount * self.applied_discount
        final_total = total_amount - discount_amount

        # VAT calculations (Philippines 12% VAT standard: Prices are VAT-Inclusive)
        vatable_sales = final_total / 1.12
        vat_amount = final_total - vatable_sales

        self.totalsub.setText(f"Subtotal: ₱{vatable_sales:,.2f}")
        self.totalvat.setText(f"12% VAT: ₱{vat_amount:,.2f}")
        self.totalgrand.setText(f"Grand Total: ₱{final_total:,.2f}")

        return vatable_sales, vat_amount, final_total, discount_amount

    # --- DISCOUNT HANDLING ---
    def apply_discount(self):
        if self.itemList.rowCount() == 0:
            QMessageBox.information(self.MainWindow, "Empty Cart", "Add items to cart before applying discount.")
            return

        discount_percent, ok = QInputDialog.getDouble(
            self.MainWindow, "Apply Discount", "Enter discount percentage (e.g. 20 for Senior/PWD):", 0, 0, 100, 1
        )
        if ok:
            self.applied_discount = discount_percent / 100.0
            self.calculate_totals()
            QMessageBox.information(self.MainWindow, "Discount Applied", f"{discount_percent}% discount applied.")

    # --- PAYMENT & IMMEDIATE RECEIPT ---
    def process_payment(self):
        if self.itemList.rowCount() == 0:
            QMessageBox.warning(self.MainWindow, "Empty Cart", "Cannot process payment with an empty cart!")
            return

        vatable_sales, vat_amount, grand_total, discount_amount = self.calculate_totals()

        cash_tendered, ok = QInputDialog.getDouble(
            self.MainWindow, "Payment Processing", f"Grand Total Due: ₱{grand_total:,.2f}\nEnter Cash Amount Tendered:", grand_total, 0, 100000, 2
        )

        if not ok:
            return

        if cash_tendered < grand_total:
            QMessageBox.critical(self.MainWindow, "Insufficient Cash", f"Tendered amount (₱{cash_tendered:,.2f}) is less than Total Due (₱{grand_total:,.2f}).")
            return

        change = cash_tendered - grand_total

        # Generate Receipt Text
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        receipt_text = f"{'POS OFFICIAL RECEIPT':^40}\n"
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
            receipt_text += f"{'Discount:':<25} -₱{discount_amount:>10,.2f}\n"
        receipt_text += f"{'GRAND TOTAL:':<25} ₱{grand_total:>10,.2f}\n"
        receipt_text += f"{'Cash Tendered:':<25} ₱{cash_tendered:>10,.2f}\n"
        receipt_text += f"{'Change:':<25} ₱{change:>10,.2f}\n"
        receipt_text += f"{'========================================':^40}\n"
        receipt_text += f"{'THANK YOU FOR YOUR PURCHASE!':^40}\n"

        # Show Receipt Dialog Immediately
        dialog = ReceiptDialog(receipt_text, self.MainWindow)
        dialog.exec()

        # Clear Cart & Reset for Next Transaction
        self.itemList.setRowCount(0)
        self.applied_discount = 0.0
        self.calculate_totals()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())