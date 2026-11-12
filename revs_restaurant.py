#!/usr/bin/env python3
"""
Revs Restaurant POS – Python + SQLite (procedural, no OOP)
Tables 1–30 | Server name validated only for Table orders
"""

import datetime, getpass, os, sqlite3, sys
from collections import defaultdict

# ── Config ──────────────────────────────────────────────────────────
RESTAURANT, TAX, CUR = "Revs Restaurant", 5.0, "Rs."
MAX_TABLES = 30
PASSWORDS = {"Admin": "Revanth123", "Staff": "12345678"}
DAYS = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
MONTHS = ("January February March April May June July August "
          "September October November December").split()
SLOTS = ["Morning", "Afternoon", "Evening"]
CATS = ["Normal Items", "Drinks", "Special Items"]
STOCK0 = {"Normal Items": 30, "Drinks": 40, "Special Items": 12}
W, SHOW = 52, 10
try:
    BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE = os.getcwd()
DB_PATH = os.path.join(BASE, "revs_restaurant.db")

# ── DB ──────────────────────────────────────────────────────────────
_conn = None

def db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn

def ex(sql, args=None, fetch=None):
    cur = db().execute(sql, args or ())
    if fetch == "one":
        r = cur.fetchone()
        return dict(r) if r else None
    if fetch == "all":
        return [dict(r) for r in cur.fetchall()]
    if fetch == "id":
        db().commit()
        return cur.lastrowid
    db().commit()
    return cur.rowcount

def many(sql, rows):
    n = db().executemany(sql, rows).rowcount
    db().commit()
    return n

def init_db():
    ex("""CREATE TABLE IF NOT EXISTS menu(
        day TEXT, session TEXT, category TEXT, item TEXT, price REAL, daily_stock INT,
        PRIMARY KEY(day, session, item))""")
    ex("""CREATE TABLE IF NOT EXISTS stock(
        date_s TEXT, day TEXT, session TEXT, category TEXT, item TEXT,
        price REAL, opening_stock INT, remaining INT,
        PRIMARY KEY(date_s, session, item))""")
    ex("""CREATE TABLE IF NOT EXISTS bills(
        bill_no INTEGER PRIMARY KEY AUTOINCREMENT,
        date_s TEXT, day TEXT, month TEXT, year INT, time_s TEXT, session TEXT,
        order_type TEXT, table_order_no TEXT, server TEXT, customer TEXT,
        phone TEXT DEFAULT '', no_of_customers INT, items_ordered TEXT,
        subtotal REAL, tax_percent REAL, tax REAL, tip_percent REAL, tip REAL, total REAL)""")
    ex("CREATE INDEX IF NOT EXISTS idx_bills_date ON bills(date_s)")
    ex("""CREATE TABLE IF NOT EXISTS bill_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, bill_no INT, date_s TEXT, day TEXT,
        month TEXT, year INT, session TEXT, item TEXT, category TEXT,
        qty INT, rate REAL, amount REAL,
        FOREIGN KEY(bill_no) REFERENCES bills(bill_no) ON DELETE CASCADE)""")
    ex("CREATE INDEX IF NOT EXISTS idx_items_bill ON bill_items(bill_no)")
    if not ex("SELECT COUNT(*) c FROM menu", fetch="one")["c"]:
        rows = []
        for d in range(7):
            for s in SLOTS:
                for cat, lst in build_menu(d, s).items():
                    for n, p in lst:
                        rows.append((DAYS[d], s, cat, n, p, STOCK0[cat]))
        many("INSERT INTO menu VALUES (?,?,?,?,?,?)", rows)
        print("  Menu seeded.")

# ── Menu data ───────────────────────────────────────────────────────
def _p(t):
    return [(n.strip(), int(p)) for n, p in (x.rsplit("=", 1) for x in t.split(","))]

POOLS = {
    "Morning": {
        "Normal Items": _p("Idli (2 pcs)=40, Plain Dosa=50, Masala Dosa=70, Medu Vada (2 pcs)=45, Ven Pongal=60, Rava Upma=40, Poori Masala=65, Onion Uttapam=70"),
        "Drinks": _p("Filter Coffee=25, Masala Tea=20, Badam Milk=40, Fresh Orange Juice=60, Sweet Lassi=50, Spiced Buttermilk=25, Hot Chocolate=70"),
        "Special Items": _p("Ghee Podi Dosa=90, Pesarattu Upma=85, Chole Bhature=110, Aloo Paratha Combo=100, Mini Tiffin Platter=150, Set Dosa Trio=95, Benne Masala Dosa=105"),
    },
    "Afternoon": {
        "Normal Items": _p("Veg Meals=120, Curd Rice=60, Lemon Rice=60, Veg Biryani=130, Chapati with Curry=80, Sambar Rice=70, Tomato Rice=65, Veg Fried Rice=110"),
        "Drinks": _p("Sweet Lime Juice=55, Watermelon Juice=50, Jaljeera=35, Sugarcane Juice=45, Mint Lemonade=40, Mango Lassi=65, Soda Sherbet=40"),
        "Special Items": _p("Chicken Biryani=180, Mutton Biryani=240, Andhra Chicken Meals=200, Paneer Butter Masala Meal=170, Fish Curry Meals=220, Prawn Fry Combo=230, Hyderabadi Dum Biryani=210"),
    },
    "Evening": {
        "Normal Items": _p("Samosa (2 pcs)=30, Veg Puff=25, Pav Bhaji=90, Masala Pav=70, Veg Sandwich=60, Bhel Puri=50, Mirchi Bajji=40, French Fries=80"),
        "Drinks": _p("Evening Chai=20, Cold Coffee=80, Chocolate Milkshake=90, Fresh Lime Soda=40, Iced Tea=60, Virgin Mojito=85, Rose Milk=45"),
        "Special Items": _p("Paneer Tikka=160, Chicken Lollipop=170, Veg Manchurian=130, Chilli Chicken=180, Tandoori Platter=280, Mushroom Pepper Fry=150, Fish Fingers=190"),
    },
}

def build_menu(day, slot):
    p = POOLS[slot]
    pick = lambda cat, idx: [p[cat][i % len(p[cat])] for i in idx]
    return {
        "Normal Items": pick("Normal Items", range(day, day + 5)),
        "Drinks": pick("Drinks", range(day, day + 4)),
        "Special Items": pick("Special Items", (day, day + 3)),
    }

def menu_items(day, slot):
    rows = ex(
        "SELECT category, item name, price, daily_stock remaining FROM menu "
        "WHERE day=? AND session=? ORDER BY CASE category "
        "WHEN 'Normal Items' THEN 1 WHEN 'Drinks' THEN 2 WHEN 'Special Items' THEN 3 ELSE 4 END, item",
        (DAYS[day], slot), "all")
    return [{"category": r["category"], "name": r["name"],
             "price": float(r["price"]), "remaining": int(r["remaining"])} for r in rows]

# ── Helpers ─────────────────────────────────────────────────────────
def now():
    return datetime.datetime.now()

def slot_of(h):
    return "Morning" if 5 <= h < 12 else "Afternoon" if 12 <= h < 17 else "Evening"

def fmt(d):
    return d.strftime("%d-%m-%Y")

def parse_date(t):
    try:
        return datetime.datetime.strptime(str(t).replace("/", "-"), "%d-%m-%Y").date()
    except ValueError:
        return None

def money(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return "0.00"

def banner(t):
    print(f"\n{'=' * W}\n{t.center(W)}\n{'=' * W}")

def clean(s):
    return "".join(c for c in s if c.isprintable()).strip()

def ask(prompt, parse=None, ok=lambda v: True, err="Please enter a value.", default=None):
    parse = parse or clean
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            v = parse(raw)
        except ValueError:
            v = None
        if v not in (None, "") and ok(v):
            return v
        print("  " + err)

def ask_num(prompt, lo, hi, cast=int, default=None):
    return ask(prompt, cast, lambda v: lo <= v <= hi, f"Enter {lo}–{hi}.", default)

def ask_date(prompt):
    return ask(prompt, parse_date, err="Use DD-MM-YYYY.")

def parse_phone(t):
    if any(c not in "0123456789 -+()" for c in t):
        return None
    d = "".join(c for c in t if c.isdigit())
    if len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d[0] == "0":
        d = d[1:]
    return d if len(d) == 10 else None

def ask_pw(prompt):
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return getpass.getpass(prompt)
    sys.stdout.write(prompt)
    sys.stdout.flush()
    if os.name == "nt":
        import msvcrt
        getch, restore = msvcrt.getwch, (lambda: None)
    else:
        import termios, tty
        fd, saved = sys.stdin.fileno(), termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(fd)
        getch = lambda: sys.stdin.read(1)
        restore = lambda: termios.tcsetattr(fd, termios.TCSADRAIN, saved)
    pw = ""
    try:
        while True:
            ch = getch()
            if ch in ("\r", "\n"):
                break
            if ch == "\x03":
                raise KeyboardInterrupt
            if os.name == "nt" and ch in ("\x00", "\xe0"):
                getch()
            elif ch in ("\b", "\x7f"):
                if pw:
                    pw = pw[:-1]
                    sys.stdout.write("\b \b")
            elif ch.isprintable():
                pw += ch
                sys.stdout.write("●")
            sys.stdout.flush()
    finally:
        restore()
    print()
    return pw

def yn(prompt):
    return ask(prompt, lambda s: {"y": True, "yes": True, "n": False, "no": False}.get(s.lower()),
               err="Y or N.")

def choose(opts, prompt="  Select: "):
    for i, o in enumerate(opts, 1):
        print(f"  {i}. {o}")
    return ask_num(prompt, 1, len(opts))

def table(cols, rows, ind="  "):
    line = lambda cells: ind + "".join(f"{str(c):{a}{w}}" for c, (_, w, a) in zip(cells, cols))
    print(line([h for h, _, _ in cols]))
    for r in rows:
        print(line(r))

def print_menu(items, cart=None):
    cart = cart or {}
    cur, avail = None, 0
    for i, it in enumerate(items, 1):
        if it["category"] != cur:
            cur = it["category"]
            print(f"\n  --- {cur.upper()} ---")
        left = it["remaining"] - cart.get(it["name"], 0)
        avail += left > 0
        st = "NOT AVAILABLE" if left <= 0 else f"Available ({left} left)" + ("  <- hurry!" if left <= 5 else "")
        print(f"  {i:>2}. {it['name']:<27}{money(it['price']):>9}   {st}")
    print(f"\n  Items available: {avail} of {len(items)}")

def validate_server(name):
    name = name.strip()
    if len(name) < 2:
        raise ValueError("Server name too short")
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ .'-" for c in name):
        raise ValueError("Server name: letters, spaces, dots, hyphens only")
    return name.title()

def render_bill(b):
    tbl = b["order_type"] == "Table"
    row = lambda lb, v: f"{lb:<40}{money(v):>12}"
    L = ["=" * W, RESTAURANT.upper().center(W), "BILL".center(W), "=" * W,
         f"Bill No : {b['bill_no']:<10} Date    : {b['date_s']} ({b['day']})",
         f"Time    : {b['time_s']:<10} Session : {b['session']}"]
    if tbl:
        L += [f"Table No: {b['table_order_no']}", f"Server  : {b['server']}"]
    else:
        L.append(f"Take Away - Order No: {b['table_order_no']}")
    L += [f"Customer: {b['customer']}", f"Phone   : {b['phone'] or '-'}",
          f"No. of customers: {b['guests']}", "-" * W,
          f"{'Item':<24}{'Qty':>5}{'Rate':>11}{'Amount':>12}", "-" * W]
    for n, _, q, rt, am in b["items"]:
        if len(n) > 23:
            L.append(n)
            n = ""
        L.append(f"{n:<24}{'* ' + str(q):>5}{money(rt):>11}{money(am):>12}")
    L += ["-" * W, row("Sub-total", b["subtotal"]), row(f"Tax ({TAX:g}%)", b["tax"])]
    if tbl and b["tip_percent"]:
        L.append(row(f"Tip ({b['tip_percent']:g}%)", b["tip"]))
    L += ["=" * W, row(f"TOTAL ({CUR})", b["total"]), "=" * W,
          f"Thank you! Please visit {RESTAURANT} again.".center(W)]
    return "\n".join(L)

# ── Stock ───────────────────────────────────────────────────────────
def slot_stock(dt, slot, change=None):
    ds, day = fmt(dt.date()), DAYS[dt.weekday()]
    menu = menu_items(dt.weekday(), slot)
    have = {r["item"]: r for r in ex("SELECT * FROM stock WHERE date_s=? AND session=?", (ds, slot), "all")}
    out = []
    for it in menu:
        r = have.get(it["name"])
        if not r:
            ex("INSERT INTO stock VALUES (?,?,?,?,?,?,?,?)",
               (ds, day, slot, it["category"], it["name"], it["price"], it["remaining"], it["remaining"]))
            rem, price = it["remaining"], it["price"]
        else:
            price, rem = float(r["price"]), int(r["remaining"])
            if abs(price - it["price"]) > 0.001:
                ex("UPDATE stock SET price=? WHERE date_s=? AND session=? AND item=?",
                   (it["price"], ds, slot, it["name"]))
                price = it["price"]
        dlt = (change or {}).get(it["name"])
        if dlt:
            rem = max(0, rem + dlt)
            if dlt > 0:
                op = (int(r["opening_stock"]) if r else it["remaining"]) + dlt
                ex("UPDATE stock SET remaining=?, opening_stock=? WHERE date_s=? AND session=? AND item=?",
                   (rem, op, ds, slot, it["name"]))
            else:
                ex("UPDATE stock SET remaining=? WHERE date_s=? AND session=? AND item=?",
                   (rem, ds, slot, it["name"]))
        out.append({"category": it["category"], "name": it["name"], "price": price, "remaining": rem})
    return out

# ── Orders ──────────────────────────────────────────────────────────
def next_ta(ds):
    r = ex("SELECT COALESCE(MAX(CAST(table_order_no AS INT)),0) m FROM bills "
           "WHERE date_s=? AND order_type='Take Away'", (ds,), "one")
    return int(r["m"]) + 1

def save_bill(b):
    txt = "; ".join(f"{n} * {q}" for n, _, q, _, _ in b["items"])
    bn = ex(
        "INSERT INTO bills VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (b["date_s"], b["day"], b["month"], b["year"], b["time_s"], b["session"],
         b["order_type"], b["table_order_no"], b["server"], b["customer"], b["phone"],
         b["guests"], txt, b["subtotal"], TAX, b["tax"], b["tip_percent"], b["tip"], b["total"]),
        "id")
    for n, c, q, rt, am in b["items"]:
        ex("INSERT INTO bill_items VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?)",
           (bn, b["date_s"], b["day"], b["month"], b["year"], b["session"], n, c, q, rt, am))
    return bn

def show_cart(cart, by):
    print("\n  Your order so far:")
    for i, (n, q) in enumerate(cart.items(), 1):
        print(f"   {i}. {n:<27} * {q:<3} {money(by[n]['price'] * q):>10}")
    print(f"   {'Sub-total':<33}{money(sum(by[k]['price'] * q for k, q in cart.items())):>10}")

def new_order():
    n = now()
    sl, ds = slot_of(n.hour), fmt(n.date())
    banner("NEW ORDER")
    print(f"  {DAYS[n.weekday()]}, {ds}  {n:%H:%M}   Session: {sl}\n")
    is_tbl = choose(["Table", "Order - Take Away"]) == 1
    cust = ask("  Customer name: ")
    phone = ask("  Phone: ", parse_phone, err="10-digit phone.")
    guests = ask_num("  Customers: ", 1, 500)

    if is_tbl:
        tno = ask_num(f"  Table (1-{MAX_TABLES}): ", 1, MAX_TABLES)
        while True:
            try:
                server = validate_server(ask("  Server name: "))
                break
            except ValueError as e:
                print(f"  ! {e}")
        otype, number, server_s = "Table", str(tno), server
    else:
        number = str(next_ta(ds))
        print(f"  Take-away #: {number}")
        otype, server_s = "Take Away", "-"

    items = slot_stock(n, sl)
    if not items:
        print("  No items.")
        return
    by, cart = {i["name"]: i for i in items}, {}
    print(f"\n  MENU - {DAYS[n.weekday()]} {sl}")
    print_menu(items, cart)

    while True:
        cmd = input("\n  # | M=menu V=view R=remove D=done C=cancel : ").strip().lower()
        if cmd == "m":
            print_menu(items, cart)
        elif cmd == "v":
            show_cart(cart, by) if cart else print("  Empty.")
        elif cmd == "r":
            if not cart:
                print("  Nothing.")
                continue
            show_cart(cart, by)
            k = ask_num("  Remove line (0=none): ", 0, len(cart))
            if k:
                g = list(cart)[k - 1]
                del cart[g]
                print(f"  Removed {g}.")
        elif cmd == "c":
            print("  Cancelled.")
            return
        elif cmd == "d":
            if not cart:
                print("  Order something.")
                continue
            show_cart(cart, by)
            if yn("\n  Place order? (Y/N): "):
                break
        elif cmd.isdigit() and 1 <= int(cmd) <= len(items):
            it = items[int(cmd) - 1]
            left = it["remaining"] - cart.get(it["name"], 0)
            if left <= 0:
                print(f"  {it['name']} unavailable.")
                continue
            q = ask_num(f"  Qty of {it['name']} (0-{left}): ", 0, left)
            if q:
                cart[it["name"]] = cart.get(it["name"], 0) + q
                print(f"  +{q} x {it['name']} ({left - q} left)")
        else:
            print("  Invalid.")

    sub = round(sum(by[k]["price"] * q for k, q in cart.items()), 2)
    tip_pct = ask_num("  Tip % (0=none): ", 0, 100, float, 0.0) if is_tbl else 0.0
    tax, tip = round(sub * TAX / 100, 2), round(sub * tip_pct / 100, 2)
    bill = {
        "date_s": ds, "day": DAYS[n.weekday()], "month": MONTHS[n.month - 1], "year": n.year,
        "time_s": n.strftime("%H:%M:%S"), "session": sl, "order_type": otype,
        "table_order_no": number, "server": server_s, "customer": cust, "phone": phone,
        "guests": guests, "subtotal": sub, "tax": tax, "tip_percent": tip_pct, "tip": tip,
        "total": round(sub + tax + tip, 2),
        "items": [(k, by[k]["category"], q, by[k]["price"], round(by[k]["price"] * q, 2))
                  for k, q in cart.items()],
    }
    bill["bill_no"] = save_bill(bill)
    slot_stock(n, sl, {k: -q for k, q in cart.items()})
    print("\n" + render_bill(bill) + f"\n\n  Bill #{bill['bill_no']} saved.")

# ── View / Reports ──────────────────────────────────────────────────
def date_list(a, b):
    out, d = [], a
    while d <= b:
        out.append(fmt(d))
        d += datetime.timedelta(days=1)
    return out

def rows_in(table_name, a, b):
    ds = date_list(a, b)
    if not ds:
        return []
    ph = ",".join("?" * len(ds))
    order = "bill_no" if table_name == "bills" else ("bill_no, id" if table_name == "bill_items" else "date_s")
    return ex(f"SELECT * FROM {table_name} WHERE date_s IN ({ph}) ORDER BY {order}", ds, "all")

def ask_period():
    today = now().date()
    print("\n  Period:")
    c = choose(["Today", "Specific date", "Last 7 days", "This month", "Custom"])
    if c == 1:
        a = b = today
    elif c == 2:
        a = b = ask_date("  Date: ")
    elif c == 3:
        a, b = today - datetime.timedelta(days=6), today
    elif c == 4:
        a, b = today.replace(day=1), today
    else:
        a, b = sorted((ask_date("  From: "), ask_date("  To: ")))
    lb = fmt(a) if a == b else f"{fmt(a)} to {fmt(b)}"
    return a, b, lb

def view_bills():
    a, b, lb = ask_period()
    bills, lines = rows_in("bills", a, b), rows_in("bill_items", a, b)
    banner(f"BILLS - {lb}")
    if not bills:
        print("  None.")
        return
    table([("Bill", 6, "<"), ("Date", 12, "<"), ("Time", 9, "<"), ("Type", 10, "<"),
           ("No", 4, "<"), ("Customer", 16, "<"), ("Phone", 12, "<"), ("Total", 12, ">")],
          [(x["bill_no"], x["date_s"], x["time_s"], x["order_type"], x["table_order_no"],
            str(x["customer"])[:15], x["phone"] or "-", money(x["total"])) for x in bills])
    print(f"\n  {len(bills)} bill(s), {CUR} {money(sum(float(x['total']) for x in bills))}")
    while True:
        raw = input("\n  Bill No (Enter=back): ").strip()
        if not raw:
            return
        bil = next((x for x in bills if str(x["bill_no"]) == raw), None)
        if not bil:
            print("  Not found.")
            continue
        its = [(i["item"], i["category"], int(i["qty"]), float(i["rate"]), float(i["amount"]))
               for i in lines if i["bill_no"] == bil["bill_no"]]
        bill = {
            "bill_no": bil["bill_no"], "date_s": bil["date_s"], "day": bil["day"],
            "time_s": bil["time_s"], "session": bil["session"], "order_type": bil["order_type"],
            "table_order_no": bil["table_order_no"], "server": bil["server"],
            "customer": bil["customer"], "phone": bil["phone"],
            "guests": bil["no_of_customers"], "subtotal": float(bil["subtotal"]),
            "tax": float(bil["tax"]), "tip_percent": float(bil["tip_percent"]),
            "tip": float(bil["tip"]), "total": float(bil["total"]), "items": its,
        }
        print("\n" + render_bill(bill))

def sales_report():
    a, b, lb = ask_period()
    bills, lines, offered = rows_in("bills", a, b), rows_in("bill_items", a, b), rows_in("stock", a, b)
    if not bills:
        banner(f"SALES REPORT - {lb}")
        print("  No sales.")
        return
    daily = defaultdict(lambda: defaultdict(int))
    sess = defaultdict(lambda: defaultdict(int))
    cats = defaultdict(lambda: defaultdict(int))
    items = defaultdict(lambda: defaultdict(int))
    cat_of = {r["item"]: r["category"] for r in offered}
    for bil in bills:
        d = parse_date(bil["date_s"])
        daily[d]["bills"] += 1
        daily[d]["income"] += float(bil["total"])
        sess[bil["session"]]["bills"] += 1
        sess[bil["session"]]["income"] += float(bil["total"])
    for r in lines:
        q, am = int(r["qty"]), float(r["amount"])
        d = parse_date(r["date_s"])
        daily[d]["items"] += q
        cats[r["category"]]["units"] += q
        cats[r["category"]]["revenue"] += am
        items[r["item"]]["units"] += q
        items[r["item"]]["revenue"] += am
        cat_of[r["item"]] = r["category"]
    for name in cat_of:
        items[name]["units"] += 0
    ranked = sorted(items.items(), key=lambda kv: (-kv[1]["units"], kv[0]))
    k = max(1, len(ranked) // 3)
    top = ranked[:k]
    low = ranked[-k:][::-1] if len(ranked) > 1 else []
    mid = ranked[k:-k] if len(ranked) > 1 else []
    tot = lambda col: sum(float(x[col]) for x in bills)
    banner(f"SALES REPORT - {lb}")
    for t, v in [("Bills", len(bills)), ("Customers", int(tot("no_of_customers"))),
                 ("Items sold", sum(c["units"] for c in cats.values())),
                 ("Sub-total", f"{CUR} {money(tot('subtotal'))}"),
                 ("Tax", f"{CUR} {money(tot('tax'))}"),
                 ("Tips", f"{CUR} {money(tot('tip'))}"),
                 ("TOTAL", f"{CUR} {money(tot('total'))}")]:
        print(f"  {t:<20}: {v}")
    print("\n  By day")
    table([("Date", 12, "<"), ("Day", 11, "<"), ("Bills", 6, ">"), ("Items", 7, ">"), ("Income", 13, ">")],
          [(fmt(d), DAYS[d.weekday()], e["bills"], e["items"], money(e["income"]))
           for d, e in sorted(daily.items())], "    ")
    print("\n  By session")
    table([("Session", 11, "<"), ("Bills", 6, ">"), ("Income", 13, ">")],
          [(s, sess[s]["bills"], money(sess[s]["income"])) for s in SLOTS if s in sess], "    ")
    print("\n  By category")
    table([("Category", 15, "<"), ("Sold", 11, ">"), ("Revenue", 13, ">")],
          [(c, cats[c]["units"], money(cats[c]["revenue"])) for c in CATS if c in cats], "    ")
    for lbl, tier in (("MOST POPULAR", top), ("NORMAL", mid), ("LEAST SOLD", low)):
        print(f"\n  {lbl}" + ("" if tier else "\n    (none)"))
        if tier:
            table([("Item", 28, "<"), ("Cat", 15, "<"), ("Sold", 6, ">"), ("Rev", 12, ">")],
                  [(n, cat_of[n], s["units"], money(s["revenue"])) for n, s in tier[:SHOW]], "    ")

# ── Admin ───────────────────────────────────────────────────────────
def ask_scope():
    d = ask_num("  Day 1=Mon..7=Sun (0=all): ", 0, 7)
    s = ask_num("  Session 1=M 2=A 3=E (0=all): ", 0, 3)
    return [(i, sl) for i in (range(7) if d == 0 else [d - 1])
            for sl in (SLOTS if s == 0 else [SLOTS[s - 1]])]

def pick_item():
    d = choose(DAYS) - 1
    s = SLOTS[choose(SLOTS) - 1]
    items = menu_items(d, s)
    if not items:
        print("  Empty.")
        return None
    print(f"\n  MENU - {DAYS[d]} {s}")
    table([("No", 4, "<"), ("Item", 28, "<"), ("Cat", 15, "<"), ("Price", 9, ">"), ("Stock", 12, ">")],
          [(i, it["name"], it["category"], money(it["price"]), it["remaining"])
           for i, it in enumerate(items, 1)])
    return items[ask_num("\n  Item #: ", 1, len(items)) - 1], d, s

def add_item():
    tg = ask_scope()
    cat = CATS[choose(CATS, "  Category: ") - 1]
    name = ask("  Name: ")
    price = ask_num("  Price: ", 0.01, 1e5, lambda t: round(float(t), 2))
    stock = ask_num("  Daily stock: ", 0, 10000)
    added = 0
    for d, s in tg:
        if not ex("SELECT 1 FROM menu WHERE day=? AND session=? AND item=?",
                  (DAYS[d], s, name), "one"):
            ex("INSERT INTO menu VALUES (?,?,?,?,?,?)", (DAYS[d], s, cat, name, price, stock))
            added += 1
    print(f"  Added to {added} menu(s).")

def remove_item():
    pk = pick_item()
    if not pk:
        return
    it, d, s = pk
    everywhere = yn(f"  Remove '{it['name']}' everywhere? (Y=all N=only {DAYS[d]} {s}): ")
    if everywhere:
        n = ex("DELETE FROM menu WHERE item=?", (it["name"],))
    else:
        n = ex("DELETE FROM menu WHERE item=? AND day=? AND session=?", (it["name"], DAYS[d], s))
    print(f"  Removed {n}.")

def edit_item():
    pk = pick_item()
    if not pk:
        return
    it, d, s = pk
    price = ask_num(f"  Price (now {money(it['price'])}): ", 0.01, 1e5,
                    lambda t: round(float(t), 2), it["price"])
    stock = ask_num(f"  Daily stock (now {it['remaining']}): ", 0, 10000, int, it["remaining"])
    everywhere = yn(f"  Apply everywhere? (Y=all N=only {DAYS[d]} {s}): ")
    if everywhere:
        ex("UPDATE menu SET price=?, daily_stock=? WHERE item=?", (price, stock, it["name"]))
    else:
        ex("UPDATE menu SET price=?, daily_stock=? WHERE item=? AND day=? AND session=?",
           (price, stock, it["name"], DAYS[d], s))
    print("  Saved.")

def change_stock(sign):
    n = now()
    print(f"\n  Today {DAYS[n.weekday()]}, session {slot_of(n.hour)}.")
    sl = SLOTS[choose(SLOTS) - 1]
    items = slot_stock(n, sl)
    if not items:
        print("  Empty.")
        return
    print_menu(items)
    it = items[ask_num("\n  Item #: ", 1, len(items)) - 1]
    top = 10000 if sign > 0 else it["remaining"]
    if top == 0:
        print(f"  {it['name']} empty.")
        return
    q = ask_num(f"  How many ({'add' if sign > 0 else 'remove'} 0-{top}): ", 0, top)
    if q:
        slot_stock(n, sl, {it["name"]: sign * q})
        print(f"  {it['name']}: {it['remaining']} → {it['remaining'] + sign * q}")

def preview_menu():
    d = choose(DAYS) - 1
    s = SLOTS[choose(SLOTS) - 1]
    banner(f"MENU - {DAYS[d]} {s}")
    items = menu_items(d, s)
    print_menu(items) if items else print("  Empty.")

def admin_menu():
    acts = [
        ("Add item", add_item), ("Remove item", remove_item),
        ("Edit price/stock", edit_item),
        ("Add today's stock", lambda: change_stock(+1)),
        ("Remove today's stock", lambda: change_stock(-1)),
        ("Preview menu", preview_menu),
    ]
    while True:
        banner("ADMIN - MENU & STOCK")
        for i, (t, _) in enumerate(acts, 1):
            print(f"  {i}. {t}")
        ch = input("  0. Back\n\n  Select: ").strip()
        if ch == "0":
            return
        if ch.isdigit() and 1 <= int(ch) <= len(acts):
            try:
                acts[int(ch) - 1][1]()
            except Exception as e:
                print(f"\n  ! {e}")
        else:
            print("  Invalid.")

def today_menu():
    n = now()
    sl = slot_of(n.hour)
    items = slot_stock(n, sl)
    banner(f"TODAY - {DAYS[n.weekday()]} {sl}")
    print_menu(items) if items else print("  Empty.")

# ── Main ────────────────────────────────────────────────────────────
def login():
    while True:
        banner("WELCOME TO REVS RESTAURANT")
        p = input("  1. Admin  2. Staff  0. Exit\n\n  Select: ").strip()
        if p == "0":
            return None
        if p not in ("1", "2"):
            print("  Invalid.")
            continue
        role = ("Admin", "Staff")[int(p) - 1]
        for _ in range(3):
            if ask_pw(f"  {role} password: ") == PASSWORDS[role]:
                return role
            print("  Wrong.")
        print("  Too many attempts.")

def main_menu(role):
    acts = [
        ("New Order", new_order), ("Today's Menu", today_menu),
        ("View Bills", view_bills), ("Sales Report", sales_report),
        ("Preview Menu", preview_menu),
    ]
    if role == "Admin":
        acts.append(("Manage Menu & Stock", admin_menu))
    while True:
        n = now()
        banner("REVS RESTAURANT")
        print(f"  {DAYS[n.weekday()]}, {fmt(n.date())}  {n:%H:%M}  "
              f"Session: {slot_of(n.hour)}  User: {role}  Tables: 1-{MAX_TABLES}\n")
        for i, (t, _) in enumerate(acts, 1):
            print(f"  {i}. {t}")
        ch = input("  0. Logout\n\n  Select: ").strip()
        if ch == "0":
            return
        if ch.isdigit() and 1 <= int(ch) <= len(acts):
            try:
                acts[int(ch) - 1][1]()
            except Exception as e:
                print(f"\n  ! {e}")
        else:
            print("  Invalid.")

def main():
    try:
        init_db()
    except Exception as e:
        print(f"\n  DB error: {e}\n  Path: {DB_PATH}")
        return
    while True:
        role = login()
        if not role:
            break
        main_menu(role)
    print("\n  Goodbye!\n")
    if _conn:
        _conn.close()

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\n  Goodbye!\n")
