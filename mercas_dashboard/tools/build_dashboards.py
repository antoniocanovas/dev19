#!/usr/bin/env python3
""" Builds the spreadsheets of the dashboards of Mercas (data/files/*.json).

The spreadsheets are written from here, not by hand: run it after a change and upgrade the
module. They can be retouched in Odoo with the editor of spreadsheet_dashboard_oca (OCA
spreadsheet), but such a change stays in that database: to keep it, export the spreadsheet
and bring the change here.

    python3 mercas_dashboard/tools/build_dashboards.py

Each dashboard has a sheet "Dashboard", the one shown, and a sheet "Data" with the figures by
period, worked out from the sales (or purchases) of each day: the day, the week, the month and
the year up to today, against the period before and the same one a year before, as the
management summary sent by email. The section "In the period" follows the period chosen in the
filter of the dashboard, against the period before.

The texts in English go through _t(): their Spanish translation is in i18n/es.po.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = os.path.join(HERE, "..", "data", "files")

VERSION = "18.5.10"

# Colours: those of the management summary
PRIMARY = "#714B67"
PREVIOUS = "#6ea8fe"
LAST_YEAR = "#adb5bd"
GREEN = "#198754"
RED = "#dc3545"
TITLE_COLOR = "#01666b"
TEXT_COLOR = "#434343"
AGE_COLORS = ["#198754", "#ffc107", "#fd7e14", "#dc3545", "#842029"]

MONEY = "#,##0.00 [$€]"
MONEY_KG = "#,##0.00 [$€]\"/kg\""
KG = "#,##0\" kg\""
INTEGER = "#,##0"
PERCENT = "+0.0%;-0.0%;0.0%"
PERCENT_PLAIN = "0.0%"
DATE = "dd/mm/yyyy"

# Ids of the global filters (stable: the dashboards edited in Odoo keep them)
F_PERIOD = "mercas-period"
F_PARTNER = "mercas-partner"
F_PRODUCT = "mercas-product"
F_CATEGORY = "mercas-category"
F_USER = "mercas-user"

DATA_ROWS = 5000  # rows of the sheet Data: the days of the history of the pivots


def col_name(index):
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def t(text):
    """ A translated text in a cell. """
    return '=_t("%s")' % text.replace('"', '""')


class Book:
    """ The spreadsheet: its sheets, styles, formats, borders, pivots, lists and filters. """

    def __init__(self):
        self.sheets = []
        self.styles = {}
        self.formats = {}
        self.borders = {}
        self.pivots = {}
        self.lists = {}
        self.filters = []
        self.figure_ids = 0

    def _registry_id(self, registry, value):
        key = json.dumps(value, sort_keys=True)
        for registry_id, existing in registry.items():
            if json.dumps(existing, sort_keys=True) == key:
                return int(registry_id)
        registry_id = len(registry) + 1
        registry[str(registry_id)] = value
        return registry_id

    def style_id(self, style):
        return self._registry_id(self.styles, style)

    def format_id(self, fmt):
        return self._registry_id(self.formats, fmt)

    def border_id(self, border):
        return self._registry_id(self.borders, border)

    def figure_id(self, prefix):
        self.figure_ids += 1
        return "%s-%s" % (prefix, self.figure_ids)

    def sheet(self, sheet_id, name, cols=26, rows=100, visible=True):
        sheet = Sheet(self, sheet_id, name, cols, rows)
        sheet.visible = visible
        self.sheets.append(sheet)
        return sheet

    def add_pivot(self, pivot_id, name, model, domain, measures, rows=(), columns=(), matching=None,
                  sorted_measure=None):
        self.pivots[str(pivot_id)] = {
            "type": "ODOO",
            "id": str(pivot_id),
            "formulaId": str(pivot_id),
            "name": name,
            "model": model,
            "domain": domain,
            "context": {},
            "measures": [
                {"id": "%s:%s" % (field, aggregator), "fieldName": field, "aggregator": aggregator}
                for field, aggregator in measures
            ],
            "rows": list(rows),
            "columns": list(columns),
            "sortedColumn": {"measure": sorted_measure, "order": "desc", "domain": []} if sorted_measure else None,
            "fieldMatching": matching or {},
        }

    def add_list(self, list_id, name, model, domain, columns, order_by, matching=None):
        self.lists[str(list_id)] = {
            "id": str(list_id),
            "name": name,
            "model": model,
            "domain": domain,
            "context": {},
            "columns": columns,
            "orderBy": order_by,
            "fieldMatching": matching or {},
        }

    def data(self):
        return {
            "version": VERSION,
            "sheets": [sheet.data() for sheet in self.sheets],
            "styles": self.styles,
            "formats": self.formats,
            "borders": self.borders,
            "revisionId": "START_REVISION",
            "uniqueFigureIds": True,
            "settings": {
                "locale": {
                    "name": "Spanish",
                    "code": "es_ES",
                    "thousandsSeparator": ".",
                    "decimalSeparator": ",",
                    "dateFormat": "dd/mm/yyyy",
                    "timeFormat": "hh:mm:ss",
                    "formulaArgSeparator": ";",
                    "weekStart": 1,
                },
            },
            "pivots": self.pivots,
            "pivotNextId": max([int(key) for key in self.pivots] or [0]) + 1,
            "customTableStyles": {},
            "globalFilters": self.filters,
            "lists": self.lists,
            "listNextId": max([int(key) for key in self.lists] or [0]) + 1,
            "chartOdooMenusReferences": {},
        }


class Sheet:

    def __init__(self, book, sheet_id, name, cols, rows):
        self.book = book
        self.id = sheet_id
        self.name = name
        self.col_number = cols
        self.row_number = rows
        self.cells = {}
        self.styles = {}
        self.formats = {}
        self.borders = {}
        self.figures = []
        self.cols = {}
        self.rows = {}
        self.merges = []
        self.conditional_formats = []

    def set(self, ref, content, style=None, fmt=None, border=None):
        if content is not None:
            self.cells[ref] = content
        if style:
            self.styles[ref] = self.book.style_id(style)
        if fmt:
            self.formats[ref] = self.book.format_id(fmt)
        if border:
            self.borders[ref] = self.book.border_id(border)

    def col_size(self, col, size):
        self.cols[str(col)] = {"size": size}

    def row_size(self, row, size):
        self.rows[str(row)] = {"size": size}

    def merge(self, ref):
        self.merges.append(ref)

    def color_change(self, ref):
        """ Green when it goes up, red when it goes down. """
        for operator, color in (("isGreaterThan", GREEN), ("isLessThan", RED)):
            self.conditional_formats.append({
                "id": "%s-%s-%s" % (self.id, ref, operator),
                "ranges": [ref],
                "rule": {"type": "CellIsRule", "operator": operator, "values": ["0"],
                         "style": {"textColor": color, "bold": True}},
            })

    def figure(self, data, col, row, width, height, x=0, y=0):
        figure_id = self.book.figure_id(self.id)
        data = dict(data, chartId=figure_id)
        self.figures.append({
            "id": figure_id, "tag": "chart", "width": width, "height": height,
            "col": col, "row": row, "offset": {"x": x, "y": y}, "data": data,
        })

    def data(self):
        return {
            "id": self.id,
            "name": self.name,
            "colNumber": self.col_number,
            "rowNumber": self.row_number,
            "rows": self.rows,
            "cols": self.cols,
            "merges": self.merges,
            "cells": self.cells,
            "styles": self.styles,
            "formats": self.formats,
            "borders": self.borders,
            "conditionalFormats": self.conditional_formats,
            "dataValidationRules": [],
            "figures": self.figures,
            "tables": [],
            "areGridLinesVisible": False,
            "isVisible": self.visible,
            "headerGroups": {"ROW": [], "COL": []},
            "comments": {},
        }


# ----------------------------------------------------------------------
# Pieces shared by the dashboards
# ----------------------------------------------------------------------

TITLE = {"textColor": TITLE_COLOR, "bold": True, "fontSize": 16}
SUBTITLE = {"textColor": TEXT_COLOR, "fontSize": 9, "italic": True}
SECTION = {"textColor": TITLE_COLOR, "bold": True, "fontSize": 13}
HEADER = {"bold": True, "textColor": TEXT_COLOR, "fillColor": "#f1f3f5", "align": "center", "wrapping": "wrap",
          "verticalAlign": "middle"}
HEADER_LEFT = dict(HEADER, align="left")
LABEL = {"bold": True, "textColor": TEXT_COLOR}
VALUE = {"textColor": TEXT_COLOR}
BOTTOM = {"bottom": {"style": "thin", "color": "#CCCCCC"}}


def scorecard(title, key, baseline=None, description="", background="#F8F9FA"):
    data = {
        "type": "scorecard",
        "title": {"text": title, "bold": True, "color": TEXT_COLOR},
        "keyValue": key,
        "background": background,
        "baselineMode": "percentage",
        "baselineColorUp": "#00A04A",
        "baselineColorDown": "#DC6965",
        "humanize": False,
    }
    if baseline:
        data["baseline"] = baseline
        data["baselineDescr"] = {"text": description}
    return data


def native_chart(chart_type, title, label_range, data_sets, y_title=""):
    """ A chart of ranges of the sheet Data: [(range, colour)], the first cell the title. """
    data = {
        "type": chart_type,
        "title": {"text": title, "bold": True, "color": TEXT_COLOR},
        "background": "#FFFFFF",
        "legendPosition": "top",
        "dataSetsHaveTitle": True,
        "labelRange": label_range,
        "dataSets": [{"dataRange": data_range, "backgroundColor": color} for data_range, color in data_sets],
        "aggregated": False,
        "stacked": False,
        "humanize": True,
        "axesDesign": {"y": {"title": {"text": y_title}}},
    }
    if chart_type == "line":
        data.update(labelsAsText=True, cumulative=False, fillArea=False)
    return data


def odoo_chart(chart_type, title, model, domain, group_by, measure, matching, cumulated=False):
    """ A chart of the data of Odoo, filtered by the filters of the dashboard. """
    return {
        "type": chart_type,
        "title": {"text": title, "bold": True, "color": TEXT_COLOR},
        "background": "#FFFFFF",
        "legendPosition": "none",
        "metaData": {
            "groupBy": group_by,
            "measure": measure,
            "order": None,
            "resModel": model,
            "mode": chart_type.replace("odoo_", ""),
            "cumulated": cumulated,
            "cumulatedStart": False,
        },
        "searchParams": {
            "comparison": None,
            "context": {},
            "domain": domain,
            "groupBy": group_by,
            "orderBy": [],
        },
        "dataSets": [],
        "verticalAxisPosition": "left",
        "stacked": False,
        "cumulatedStart": False,
        "fieldMatching": matching,
    }


def matching(chains, offset=0, period=True):
    """ fieldMatching of a data source: {filter id: field chain}, the one of the period as
    (chain, "date" or "datetime"), with `offset` periods (-1: the period before). Without
    `period`, the period filter doesn't apply (the figures by day of the sheet Data, that make
    their own periods). """
    result = {}
    for filter_id, chain in chains.items():
        if filter_id == F_PERIOD:
            if period:
                result[filter_id] = {"chain": chain[0], "type": chain[1], "offset": offset}
        else:
            result[filter_id] = {"chain": chain, "type": "many2one"}
    return result


def date_filter(label, default):
    return {"id": F_PERIOD, "type": "date", "label": label, "defaultValue": default}


def relation_filter(filter_id, label, model):
    return {"id": filter_id, "type": "relation", "label": label, "modelName": model,
            "defaultValueDisplayNames": []}


def range_sum(measure_range, date_range, date_from, date_to):
    return 'SUMIFS(%s,%s,">="&%s,%s,"<="&%s)' % (measure_range, date_range, date_from, date_range, date_to)


class Periods:
    """ The periods up to today of the sheet Data, from G1: the reference date and, for the
    day, the week, the month and the year, the period, the one before and the one a year
    before, as the management summary (the year before of the day is the same weekday 52
    weeks before, of the week the whole week 52 weeks before). """

    KEYS = ("day", "week", "month", "year")
    NAMES = {"day": "Today", "week": "Week", "month": "Month", "year": "Year"}
    FIRST_ROW = 4  # row (1-based) of the day

    def __init__(self, sheet):
        self.sheet = sheet
        sheet.set("G1", t("Today"), LABEL)
        sheet.set("H1", "=TODAY()", fmt=DATE)
        sheet.set("G2", t("Monday"), LABEL)
        sheet.set("H2", "=H1-WEEKDAY(H1,2)+1", fmt=DATE)
        for col, title in zip("GHIJKLM", ("Period", "From", "To", "Before from", "Before to",
                                          "Year before from", "Year before to")):
            sheet.set("%s3" % col, t(title), HEADER)
        rows = {
            "day": ("$H$1", "$H$1", "$H$1-1", "$H$1-1", "$H$1-364", "$H$1-364"),
            "week": ("$H$2", "$H$1", "$H$2-7", "$H$1-7", "$H$2-364", "$H$2-358"),
            "month": ("DATE(YEAR($H$1),MONTH($H$1),1)", "$H$1", "EDATE(DATE(YEAR($H$1),MONTH($H$1),1),-1)",
                      "EDATE($H$1,-1)", "EDATE(DATE(YEAR($H$1),MONTH($H$1),1),-12)", "EDATE($H$1,-12)"),
            "year": ("DATE(YEAR($H$1),1,1)", "$H$1", None, None, "DATE(YEAR($H$1)-1,1,1)", "EDATE($H$1,-12)"),
        }
        for index, key in enumerate(self.KEYS):
            row = self.FIRST_ROW + index
            sheet.set("G%s" % row, t(self.NAMES[key]), LABEL)
            for col, formula in zip("HIJKLM", rows[key]):
                if formula:
                    sheet.set("%s%s" % (col, row), "=" + formula, fmt=DATE)

    def row(self, key):
        return self.FIRST_ROW + self.KEYS.index(key)

    def bounds(self, key, which="now"):
        """ Cells of the from and the to of the period: now, before or year (before). """
        row = self.row(key)
        cols = {"now": ("H", "I"), "before": ("J", "K"), "year": ("L", "M")}[which]
        return "$%s$%s" % (cols[0], row), "$%s$%s" % (cols[1], row)


def sum_formula(measure_range, date_range, bounds):
    return "=" + range_sum(measure_range, date_range, *bounds)


def chart_blocks(sheet, date_range, amount_range, first_row, series_names):
    """ The data of the three charts of the sales (or purchases) up to today, from G
    `first_row`: the week day by day, the month and the year accumulated, with the periods to
    compare. Returns the ranges of the charts. """
    blocks = {}
    # Week, day by day: this week, the week before and the same week a year before
    row = first_row
    sheet.set("G%s" % row, t("Day"), HEADER)
    for col, name in zip("HIJ", (series_names["week_now"], series_names["week_before"], series_names["week_year"])):
        sheet.set("%s%s" % (col, row), t(name), HEADER)
    for day, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
        r = row + 1 + day
        sheet.set("G%s" % r, t(name))
        sheet.set("H%s" % r, '=IF($H$2+%s<=$H$1,%s,"")' % (
            day, range_sum(amount_range, date_range, "$H$2+%s" % day, "$H$2+%s" % day)), fmt=MONEY)
        sheet.set("I%s" % r, "=" + range_sum(amount_range, date_range, "$H$2-7+%s" % day, "$H$2-7+%s" % day),
                  fmt=MONEY)
        sheet.set("J%s" % r, "=" + range_sum(amount_range, date_range, "$H$2-364+%s" % day, "$H$2-364+%s" % day),
                  fmt=MONEY)
    blocks["week"] = ("Data!G%s:G%s" % (row + 1, row + 7),
                      ["Data!%s%s:%s%s" % (col, row, col, row + 7) for col in "HIJ"])

    # Month, accumulated day by day
    row = first_row + 10
    sheet.set("G%s" % row, t("Day"), HEADER)
    for col, name in zip("HIJ", (series_names["month_now"], series_names["month_before"], series_names["month_year"])):
        sheet.set("%s%s" % (col, row), t(name), HEADER)
    month_start = "DATE(YEAR($H$1),MONTH($H$1),1)"
    starts = {"H": month_start, "I": "EDATE(%s,-1)" % month_start, "J": "EDATE(%s,-12)" % month_start}
    for day in range(1, 32):
        r = row + day
        sheet.set("G%s" % r, str(day))
        for col, start in starts.items():
            limit = "DAY($H$1)" if col == "H" else "DAY(EOMONTH(%s,0))" % start
            sheet.set("%s%s" % (col, r), '=IF(%s<=%s,%s,"")' % (
                day, limit, range_sum(amount_range, date_range, start, "%s+%s" % (start, day - 1))), fmt=MONEY)
    blocks["month"] = ("Data!G%s:G%s" % (row + 1, row + 31),
                       ["Data!%s%s:%s%s" % (col, row, col, row + 31) for col in "HIJ"])

    # Year, accumulated month by month: this year and the year before
    row = first_row + 45
    sheet.set("G%s" % row, t("Month"), HEADER)
    for col, name in zip("HI", (series_names["year_now"], series_names["year_before"])):
        sheet.set("%s%s" % (col, row), t(name), HEADER)
    for month, name in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                  "Nov", "Dec"), start=1):
        r = row + month
        sheet.set("G%s" % r, t(name))
        sheet.set("H%s" % r, '=IF(%s<=MONTH($H$1),%s,"")' % (month, range_sum(
            amount_range, date_range, "DATE(YEAR($H$1),1,1)", "EOMONTH(DATE(YEAR($H$1),%s,1),0)" % month)),
            fmt=MONEY)
        sheet.set("I%s" % r, "=" + range_sum(
            amount_range, date_range, "DATE(YEAR($H$1)-1,1,1)", "EOMONTH(DATE(YEAR($H$1)-1,%s,1),0)" % month),
            fmt=MONEY)
    blocks["year"] = ("Data!G%s:G%s" % (row + 1, row + 12),
                      ["Data!%s%s:%s%s" % (col, row, col, row + 12) for col in "HI"])
    return blocks


ROW_PX = 23  # height of a row of the sheet
CARD_W, CARD_STEP, CARD_H = 228, 238, 96  # scorecards: four in a row, 950 px
HALF_W, HALF_STEP, FULL_W = 470, 480, 950  # charts


def rows_for(pixels):
    """ Rows taken by a figure of `pixels` high, with a margin. """
    return -(-pixels // ROW_PX) + 1


def pivot_table(sheet, row, title, pivot_id, rows=10, formats=(), with_columns=False, note=None):
    """ The `rows` first rows of a pivot under `title`, in A, without total, the header row(s)
    styled, the measures with their `formats` (one by column from B). Returns the first free row
    under it. """
    sheet.set("A%s" % row, title, SECTION)
    row += 1
    if note:
        sheet.set("A%s" % row, note, SUBTITLE)
        row += 1
    if with_columns:
        # Column titles (the groups of the columns), not the row of the measures
        sheet.set("A%s" % row, "=PIVOT(%s,%s,FALSE,TRUE,100,FALSE)" % (pivot_id, rows))
    else:
        # Only the row of the measures as header
        sheet.set("A%s" % row, "=PIVOT(%s,%s,FALSE,FALSE)" % (pivot_id, rows))
    width = 1 + len(formats)
    for index in range(width):
        sheet.set("%s%s" % (col_name(index), row), None, HEADER if index else HEADER_LEFT)
    for line in range(1, rows + 1):
        for index, fmt in enumerate(formats, start=1):
            sheet.set("%s%s" % (col_name(index), row + line), None, fmt=fmt)
    return row + rows + 2


def cards(sheet, row, items, description="", background="#F8F9FA"):
    """ A row of scorecards [(title, key, baseline)] at `row`. Returns the first free row. """
    for index, (title, key, baseline) in enumerate(items):
        sheet.figure(scorecard(title, key, baseline, description if baseline else "", background),
                     col=0, row=row - 1, width=CARD_W, height=CARD_H, x=index * CARD_STEP, y=4)
    return row + rows_for(CARD_H + 4)


def period_table(sheet, row, headers, cells):
    """ The table of the periods up to today (day, week, month, year): `cells` [(col of the
    sheet Data, format)] after the name of the period. Returns the first free row. """
    for index, header in enumerate(headers):
        sheet.set("%s%s" % (col_name(index), row), t(header), HEADER if index else HEADER_LEFT)
    sheet.row_size(row - 1, 36)
    for index, key in enumerate(Periods.KEYS):
        r = row + 1 + index
        data_row = Periods.FIRST_ROW + index
        sheet.set("A%s" % r, t(Periods.NAMES[key]), LABEL, border=BOTTOM)
        for col_index, (data_col, fmt) in enumerate(cells, start=1):
            col = col_name(col_index)
            # The year has no period before to compare with
            content = None if (key == "year" and data_col == "W") else "=Data!%s%s" % (data_col, data_row)
            sheet.set("%s%s" % (col, r), content, VALUE, fmt, BOTTOM)
        sheet.color_change("C%s:D%s" % (r, r))
    return row + 5


def up_to_today_charts(sheet, row, blocks, with_year=True):
    """ The charts of the periods up to today. Returns the first free row. """
    sheet.figure(native_chart("bar", "Week, day by day", blocks["week"][0],
                              list(zip(blocks["week"][1], (PRIMARY, PREVIOUS, LAST_YEAR)))),
                 col=0, row=row - 1, width=HALF_W, height=290, y=4)
    sheet.figure(native_chart("line", "Month, accumulated", blocks["month"][0],
                              list(zip(blocks["month"][1], (PRIMARY, PREVIOUS, LAST_YEAR)))),
                 col=0, row=row - 1, width=HALF_W, height=290, x=HALF_STEP, y=4)
    row += rows_for(294)
    if with_year:
        sheet.figure(native_chart("line", "Year, accumulated by month", blocks["year"][0],
                                  list(zip(blocks["year"][1], (PRIMARY, LAST_YEAR)))),
                     col=0, row=row - 1, width=FULL_W, height=270, y=4)
        row += rows_for(274)
    return row


def dashboard_sheet(book, widths):
    sheet = book.sheet("dashboard", "Dashboard", cols=len(widths), rows=150)
    for col, size in enumerate(widths):
        sheet.col_size(col, size)
    return sheet


NOTE_PERIODS = ("Up to today: the day against yesterday and the same weekday a year before.",
                "The week, the month and the year against the period before up to the same day, and the same "
                "one a year before (the week, the whole week).")
NOTE_FILTERS = "Untaxed amounts; net kg, without the boxes. All the figures follow the filters of the dashboard."


# ----------------------------------------------------------------------
# Sales
# ----------------------------------------------------------------------

def build_sales():
    book = Book()
    book.filters = [
        date_filter("Period", "month_to_date"),
        relation_filter(F_PARTNER, "Customer", "res.partner"),
        relation_filter(F_PRODUCT, "Product", "product.product"),
        relation_filter(F_CATEGORY, "Product Category", "product.category"),
        relation_filter(F_USER, "Salesperson", "res.users"),
    ]
    chains = {F_PERIOD: ("date", "datetime"), F_PARTNER: "partner_id", F_PRODUCT: "product_id",
              F_CATEGORY: "categ_id", F_USER: "user_id"}
    sale_domain = [["kind", "=", "sale"]]
    measures = [("amount", "sum"), ("kg", "sum"), ("boxes", "sum"), ("sale_order_id", "count_distinct")]
    model = "mercas.report.goods"
    # 1: the sales of each day, the whole history (the periods are made in the sheet Data)
    book.add_pivot(1, "Sales by day", model, sale_domain, measures,
                   rows=[{"fieldName": "date", "granularity": "day", "order": "asc"}],
                   matching=matching(chains, period=False))
    # 2 and 3: the period of the filter and the one before
    book.add_pivot(2, "Sales in the period", model, sale_domain, measures, matching=matching(chains))
    book.add_pivot(3, "Sales in the period before", model, sale_domain, measures,
                   matching=matching(chains, offset=-1))
    # 4-6: the best customers, products and categories of the period
    # The name of the pivots shown is the header of their first column: in Spanish, as it isn't
    # translated (Odoo doesn't extract it)
    for pivot_id, name, field in ((4, "Clientes", "partner_id"), (5, "Productos", "product_id"),
                                  (6, "Categorías de producto", "categ_id")):
        book.add_pivot(pivot_id, name, model, sale_domain + [[field, "!=", False]],
                       [("amount", "sum"), ("kg", "sum"), ("sale_order_id", "count_distinct")],
                       rows=[{"fieldName": field}], matching=matching(chains), sorted_measure="amount:sum")

    sheet = dashboard_sheet(book, (230, 120, 100, 120, 110, 100, 90, 80))
    data = book.sheet("data", "Data", cols=40, rows=DATA_ROWS, visible=False)
    build_period_data(data, pivot_id=1, kind="sale")

    sheet.set("A1", t("Sales"), TITLE)
    sheet.set("A2", t(NOTE_FILTERS), SUBTITLE)
    sheet.set("A4", t("How we are doing, up to today"), SECTION)
    row = cards(sheet, 5, [(Periods.NAMES[key], "Data!O%s" % (Periods.FIRST_ROW + index),
                            "Data!S%s" % (Periods.FIRST_ROW + index))
                           for index, key in enumerate(Periods.KEYS)], "vs. a year before")
    row = period_table(sheet, row, ("Period", "Sales", "vs. before", "vs. a year before", "Net kg", "Price/kg",
                                    "Orders", "Boxes"),
                       (("O", MONEY), ("W", PERCENT), ("X", PERCENT), ("P", KG), ("Q", MONEY_KG),
                        ("R", INTEGER), ("N", INTEGER)))
    sheet.set("A%s" % row, t(NOTE_PERIODS[0]), SUBTITLE)
    sheet.set("A%s" % (row + 1), t(NOTE_PERIODS[1]), SUBTITLE)
    row += 3

    sheet.set("A%s" % row, t("Pace"), SECTION)
    row += 1
    for index, header in enumerate(("", "Up to today", "A year before, up to today",
                                    "A year before, in all", "Forecast at this pace")):
        sheet.set("%s%s" % (col_name(index), row), t(header) if header else "", HEADER if index else HEADER_LEFT)
    sheet.row_size(row - 1, 36)
    for index, (key, data_row) in enumerate((("month", 6), ("year", 7))):
        r = row + 1 + index
        sheet.set("A%s" % r, t(Periods.NAMES[key]), LABEL, border=BOTTOM)
        for col, data_col in zip("BCDE", ("O", "S", "Y", "Z")):
            sheet.set("%s%s" % (col, r), "=Data!%s%s" % (data_col, data_row), VALUE, MONEY, BOTTOM)
    row += 4

    sheet.set("A%s" % row, t("Sales up to today"), SECTION)
    row = up_to_today_charts(sheet, row + 1, data.chart_blocks)

    sheet.set("A%s" % row, t("In the period"), SECTION)
    sheet.set("B%s" % row, t("The period of the filter, against the period before."), SUBTITLE)
    kpis = data.period_kpis
    row = cards(sheet, row + 1, [("Sales", kpis["amount"][0], kpis["amount"][1]),
                                 ("Net kg", kpis["kg"][0], kpis["kg"][1]),
                                 ("Price/kg", kpis["price"][0], kpis["price"][1]),
                                 ("Orders", kpis["orders"][0], kpis["orders"][1])],
                "vs. the period before", background="#EFF6FF")
    sheet.figure(odoo_chart("odoo_line", "Sales by day", model, sale_domain, ["date:day"], "amount",
                            matching(chains)),
                 col=0, row=row - 1, width=FULL_W, height=250, y=4)
    row += rows_for(254)
    formats = (MONEY, KG, INTEGER)
    row = pivot_table(sheet, row, t("Best customers"), 4, 10, formats)
    row = pivot_table(sheet, row, t("Best products"), 5, 10, formats)
    pivot_table(sheet, row, t("By product category"), 6, 10, formats)
    return book


def build_period_data(sheet, pivot_id, kind):
    """ The sheet Data of the sales or the purchases: the pivot of each day in A:E and the
    periods and figures from G. """
    sheet.set("A1", "=PIVOT(%s)" % pivot_id)
    n = DATA_ROWS
    date_range = "$A$1:$A$%s" % n
    amount, kg, boxes, orders = ("$%s$1:$%s$%s" % (col, col, n) for col in "BCDE")
    periods = Periods(sheet)
    # Figures of each period: N boxes, O amount, P kg, Q price/kg, R orders, S amount a year
    # before, T kg a year before, U amount before, V kg before, W and X change against before and
    # a year before, Y amount of the whole month/year a year before, Z forecast
    for col, title in zip("NOPQRSTUVWXYZ", ("Boxes", "Amount", "Kg", "Price/kg", "Orders", "Amount year before",
                                            "Kg year before", "Amount before", "Kg before", "Change before",
                                            "Change year before", "Year before in all", "Forecast")):
        sheet.set("%s3" % col, t(title), HEADER)
    for key in Periods.KEYS:
        row = periods.row(key)
        now, before, year = (periods.bounds(key, which) for which in ("now", "before", "year"))
        sheet.set("N%s" % row, sum_formula(boxes, date_range, now))
        sheet.set("O%s" % row, sum_formula(amount, date_range, now), fmt=MONEY)
        sheet.set("P%s" % row, sum_formula(kg, date_range, now), fmt=KG)
        sheet.set("Q%s" % row, '=IFERROR(O%s/P%s,"")' % (row, row), fmt=MONEY_KG)
        sheet.set("R%s" % row, sum_formula(orders, date_range, now))
        sheet.set("S%s" % row, sum_formula(amount, date_range, year), fmt=MONEY)
        sheet.set("T%s" % row, sum_formula(kg, date_range, year), fmt=KG)
        if key != "year":
            sheet.set("U%s" % row, sum_formula(amount, date_range, before), fmt=MONEY)
            sheet.set("V%s" % row, sum_formula(kg, date_range, before), fmt=KG)
            sheet.set("W%s" % row, '=IFERROR(O%s/U%s-1,"")' % (row, row), fmt=PERCENT)
        sheet.set("X%s" % row, '=IFERROR(O%s/S%s-1,"")' % (row, row), fmt=PERCENT)
    # The whole month and year a year before, and the forecast at the pace of the days gone by
    month_row, year_row = periods.row("month"), periods.row("year")
    sheet.set("Y%s" % month_row, "=" + range_sum(amount, date_range, "$L$%s" % month_row,
                                                 "EOMONTH($L$%s,0)" % month_row), fmt=MONEY)
    sheet.set("Z%s" % month_row, "=O%s*DAY(EOMONTH($H$1,0))/DAY($H$1)" % month_row, fmt=MONEY)
    sheet.set("Y%s" % year_row, "=" + range_sum(amount, date_range, "$L$%s" % year_row,
                                                "DATE(YEAR($H$1)-1,12,31)"), fmt=MONEY)
    sheet.set("Z%s" % year_row, "=O%s*(DATE(YEAR($H$1)+1,1,1)-$H$%s)/($H$1-$H$%s+1)" % (
        year_row, year_row, year_row), fmt=MONEY)
    names = {
        "sale": {"week_now": "This week", "week_before": "Last week", "week_year": "Same week a year before",
                 "month_now": "This month", "month_before": "Last month", "month_year": "Same month a year before",
                 "year_now": "This year", "year_before": "Last year"},
    }
    names["purchase"] = names["sale"]
    sheet.chart_blocks = chart_blocks(sheet, date_range, amount, 12, names[kind])
    # The period of the filter, against the one before (pivots 2 and 3), from AB1
    sheet.set("AB1", t("In the period"), HEADER)
    sheet.set("AC1", t("Now"), HEADER)
    sheet.set("AD1", t("Before"), HEADER)
    sheet.period_kpis = {}
    measure_names = {"sale": "sale_order_id", "purchase": "purchase_order_id"}
    for index, (key, title, formula, fmt) in enumerate((
            ("amount", "Amount", '0+PIVOT.VALUE(%s,"amount:sum")', MONEY),
            ("kg", "Kg", '0+PIVOT.VALUE(%s,"kg:sum")', KG),
            ("price", "Price/kg", 'IFERROR(PIVOT.VALUE(%s,"amount:sum")/PIVOT.VALUE(%s,"kg:sum"),0)', MONEY_KG),
            ("orders", "Orders", '0+PIVOT.VALUE(%%s,"%s:count_distinct")' % measure_names[kind], INTEGER))):
        row = 2 + index
        sheet.set("AB%s" % row, t(title), LABEL)
        for col, pid in (("AC", 2), ("AD", 3)):
            sheet.set("%s%s" % (col, row), "=" + formula.replace("%s", str(pid)), fmt=fmt)
        sheet.period_kpis[key] = ("Data!AC%s" % row, "Data!AD%s" % row)


# ----------------------------------------------------------------------
# Purchases and scrap
# ----------------------------------------------------------------------

def build_purchases():
    book = Book()
    book.filters = [
        date_filter("Period", "month_to_date"),
        relation_filter(F_PARTNER, "Supplier", "res.partner"),
        relation_filter(F_PRODUCT, "Product", "product.product"),
        relation_filter(F_CATEGORY, "Product Category", "product.category"),
    ]
    chains = {F_PERIOD: ("date", "datetime"), F_PARTNER: "partner_id", F_PRODUCT: "product_id",
              F_CATEGORY: "categ_id"}
    model = "mercas.report.goods"
    purchase_domain = [["kind", "=", "purchase"]]
    scrap_domain = [["kind", "=", "scrap"]]
    measures = [("amount", "sum"), ("kg", "sum"), ("boxes", "sum"), ("purchase_order_id", "count_distinct")]
    book.add_pivot(1, "Purchases by day", model, purchase_domain, measures,
                   rows=[{"fieldName": "date", "granularity": "day", "order": "asc"}],
                   matching=matching(chains, period=False))
    book.add_pivot(2, "Purchases in the period", model, purchase_domain, measures, matching=matching(chains))
    book.add_pivot(3, "Purchases in the period before", model, purchase_domain, measures,
                   matching=matching(chains, offset=-1))
    book.add_pivot(4, "Proveedores", model, purchase_domain + [["partner_id", "!=", False]],
                   [("amount", "sum"), ("kg", "sum"), ("purchase_order_id", "count_distinct")],
                   rows=[{"fieldName": "partner_id"}], matching=matching(chains), sorted_measure="amount:sum")
    book.add_pivot(5, "Productos", model, purchase_domain, [("amount", "sum"), ("kg", "sum")],
                   rows=[{"fieldName": "product_id"}], matching=matching(chains), sorted_measure="kg:sum")
    book.add_pivot(6, "Productos", model, scrap_domain, [("kg", "sum")],
                   rows=[{"fieldName": "product_id"}], matching=matching(chains), sorted_measure="kg:sum")
    # 7: the scrap of each day; 8 and 9: the scrap of the period and the one before
    book.add_pivot(7, "Scrap by day", model, scrap_domain, [("kg", "sum")],
                   rows=[{"fieldName": "date", "granularity": "day", "order": "asc"}],
                   matching=matching(chains, period=False))
    book.add_pivot(8, "Scrap in the period", model, scrap_domain, [("kg", "sum")], matching=matching(chains))
    book.add_pivot(9, "Scrap in the period before", model, scrap_domain, [("kg", "sum")],
                   matching=matching(chains, offset=-1))
    # Lots sold out, under sale settlement, still to settle with their supplier
    lot_fields = ["name", "product_id", "partner_id", "sale_kg", "sale_amount", "supplier_amount"]
    book.add_list(1, "Lots to settle", "stock.lot",
                  [["completed", "=", True], ["invoiceable", "=", True], ["mercas_firm_negotiation", "=", False]],
                  lot_fields, [{"name": "create_date", "asc": True}],
                  matching={F_PARTNER: {"chain": "partner_id", "type": "many2one"},
                            F_PRODUCT: {"chain": "product_id", "type": "many2one"},
                            F_CATEGORY: {"chain": "product_id.categ_id", "type": "many2one"}})

    sheet = dashboard_sheet(book, (230, 120, 100, 120, 110, 100, 90, 80))
    data = book.sheet("data", "Data", cols=40, rows=DATA_ROWS, visible=False)
    build_period_data(data, pivot_id=1, kind="purchase")
    # The scrap of each day from AF, and of each period up to today and of the period
    data.set("AF1", "=PIVOT(7)")
    scrap_dates, scrap_kg = "$AF$1:$AF$%s" % DATA_ROWS, "$AG$1:$AG$%s" % DATA_ROWS
    data.set("AI3", t("Scrap kg"), HEADER)
    data.set("AJ3", t("Scrap %"), HEADER)
    for index, key in enumerate(Periods.KEYS):
        row = Periods.FIRST_ROW + index
        data.set("AI%s" % row, "=" + range_sum(scrap_kg, scrap_dates, "$H$%s" % row, "$I$%s" % row), fmt=KG)
        data.set("AJ%s" % row, '=IFERROR(AI%s/P%s,"")' % (row, row), fmt=PERCENT_PLAIN)
    data.set("AB6", t("Scrap kg"), LABEL)
    data.set("AC6", '=0+PIVOT.VALUE(8,"kg:sum")', fmt=KG)
    data.set("AD6", '=0+PIVOT.VALUE(9,"kg:sum")', fmt=KG)
    data.set("AB7", t("Scrap %"), LABEL)
    data.set("AC7", "=IFERROR(AC6/AC3,0)", fmt=PERCENT_PLAIN)
    data.set("AD7", "=IFERROR(AD6/AD3,0)", fmt=PERCENT_PLAIN)

    sheet.set("A1", t("Purchases and Scrap"), TITLE)
    sheet.set("A2", t(NOTE_FILTERS), SUBTITLE)
    sheet.set("A4", t("How we are doing, up to today"), SECTION)
    row = cards(sheet, 5, [(Periods.NAMES[key], "Data!O%s" % (Periods.FIRST_ROW + index),
                            "Data!S%s" % (Periods.FIRST_ROW + index))
                           for index, key in enumerate(Periods.KEYS)], "vs. a year before")
    row = period_table(sheet, row, ("Period", "Purchases", "vs. before", "vs. a year before", "Net kg",
                                    "Price/kg", "Scrap kg", "Scrap %"),
                       (("O", MONEY), ("W", PERCENT), ("X", PERCENT), ("P", KG), ("Q", MONEY_KG),
                        ("AI", KG), ("AJ", PERCENT_PLAIN)))
    sheet.set("A%s" % row, t(NOTE_PERIODS[0]), SUBTITLE)
    sheet.set("A%s" % (row + 1), t(NOTE_PERIODS[1]), SUBTITLE)
    sheet.set("A%s" % (row + 2), t("Scrap %: kg scrapped of the kg bought in the period."), SUBTITLE)
    row += 4

    sheet.set("A%s" % row, t("Purchases up to today"), SECTION)
    row = up_to_today_charts(sheet, row + 1, data.chart_blocks, with_year=False)

    sheet.set("A%s" % row, t("In the period"), SECTION)
    sheet.set("B%s" % row, t("The period of the filter, against the period before."), SUBTITLE)
    kpis = data.period_kpis
    row = cards(sheet, row + 1, [("Purchases", kpis["amount"][0], kpis["amount"][1]),
                                 ("Net kg", kpis["kg"][0], kpis["kg"][1]),
                                 ("Scrap kg", "Data!AC6", "Data!AD6"),
                                 ("Scrap %", "Data!AC7", "Data!AD7")],
                "vs. the period before", background="#EFF6FF")
    row = pivot_table(sheet, row, t("Suppliers"), 4, 10, (MONEY, KG, INTEGER))
    row = pivot_table(sheet, row, t("Products bought"), 5, 10, (MONEY, KG))
    row = pivot_table(sheet, row, t("Scrap by product"), 6, 10, (KG,))

    sheet.set("A%s" % row, t("Lots to settle"), SECTION)
    sheet.set("A%s" % (row + 1), t("Sold out, under sale settlement, not yet settled with the supplier."),
              SUBTITLE)
    row += 2
    for index, field in enumerate(lot_fields):
        col = col_name(index)
        sheet.set("%s%s" % (col, row), '=ODOO.LIST.HEADER(1,"%s")' % field, HEADER if index > 2 else HEADER_LEFT)
        for line in range(1, 16):
            fmt = {3: KG, 4: MONEY, 5: MONEY}.get(index)
            sheet.set("%s%s" % (col, row + line), '=ODOO.LIST(1,%s,"%s")' % (line, field), VALUE, fmt)
    return book


# ----------------------------------------------------------------------
# Debt and payments
# ----------------------------------------------------------------------

AGE_KEYS = (("0_not_due", "Not due"), ("1_30", "1-30 days"), ("2_60", "31-60 days"), ("3_90", "61-90 days"),
            ("4_over_90", "Over 90 days"))


def build_debt():
    book = Book()
    book.filters = [
        date_filter("Payments in", "month_to_date"),
        relation_filter(F_PARTNER, "Partner", "res.partner"),
    ]
    balance = "mercas.report.balance"
    payment = "mercas.report.payment"
    balance_chains = {F_PARTNER: "partner_id"}
    payment_chains = {F_PERIOD: ("date", "date"), F_PARTNER: "partner_id"}
    customer = [["kind", "=", "customer"]]
    # 1: what is owed, by kind and age
    book.add_pivot(1, "Balances", balance, [], [("residual", "sum")],
                   rows=[{"fieldName": "kind"}], columns=[{"fieldName": "age"}],
                   matching=matching(balance_chains))
    book.add_pivot(2, "Clientes", balance, customer + [["partner_id", "!=", False]],
                   [("residual", "sum")], rows=[{"fieldName": "partner_id"}],
                   columns=[{"fieldName": "age", "order": "asc"}],
                   matching=matching(balance_chains), sorted_measure="residual:sum")
    book.add_pivot(3, "Clientes", balance, [["kind", "=", "to_invoice"]], [("residual", "sum")],
                   rows=[{"fieldName": "partner_id"}], matching=matching(balance_chains),
                   sorted_measure="residual:sum")
    book.add_pivot(4, "Proveedores", balance, [["kind", "=", "supplier"], ["partner_id", "!=", False]],
                   [("residual", "sum")], rows=[{"fieldName": "partner_id"}], matching=matching(balance_chains),
                   sorted_measure="residual:sum")
    book.add_pivot(5, "Diarios", payment, [], [("amount", "sum"), ("payment_id", "count_distinct")],
                   rows=[{"fieldName": "journal_id"}], matching=matching(payment_chains),
                   sorted_measure="amount:sum")
    book.add_pivot(6, "Payments in the period before", payment, [], [("amount", "sum")],
                   matching=matching(payment_chains, offset=-1))
    # 7: the payments of each day, for those of today whatever the period
    book.add_pivot(7, "Payments by day", payment, [], [("amount", "sum")],
                   rows=[{"fieldName": "date", "granularity": "day", "order": "asc"}],
                   matching=matching(payment_chains, period=False))

    sheet = dashboard_sheet(book, (230, 110, 110, 110, 110, 110, 120, 50))
    data = book.sheet("data", "Data", cols=12, rows=DATA_ROWS, visible=False)
    for ref, label in (("A1", "Customers owe us"), ("A2", "Overdue"), ("A3", "We owe suppliers"),
                       ("A4", "To invoice to customers"), ("A5", "Collected in the period"),
                       ("A6", "Collected in the period before"), ("A7", "Collected today")):
        data.set(ref, t(label), LABEL)
    data.set("B1", '=0+PIVOT.VALUE(1,"residual:sum","kind","customer")', fmt=MONEY)
    data.set("B2", '=B1-PIVOT.VALUE(1,"residual:sum","kind","customer","age","0_not_due")', fmt=MONEY)
    data.set("B3", '=0+PIVOT.VALUE(1,"residual:sum","kind","supplier")', fmt=MONEY)
    data.set("B4", '=0+PIVOT.VALUE(1,"residual:sum","kind","to_invoice")', fmt=MONEY)
    data.set("B5", '=0+PIVOT.VALUE(5,"amount:sum")', fmt=MONEY)
    data.set("B6", '=0+PIVOT.VALUE(6,"amount:sum")', fmt=MONEY)
    data.set("D1", "=PIVOT(7)")
    data.set("B7", "=" + range_sum("$E$1:$E$%s" % DATA_ROWS, "$D$1:$D$%s" % DATA_ROWS, "TODAY()", "TODAY()"),
             fmt=MONEY)
    # The debt of the customers by age, for its chart
    data.set("G1", t("Age"), HEADER)
    data.set("H1", t("Customers owe us"), HEADER)
    for index, (age, name) in enumerate(AGE_KEYS):
        data.set("G%s" % (index + 2), t(name))
        data.set("H%s" % (index + 2), '=0+PIVOT.VALUE(1,"residual:sum","kind","customer","age","%s")' % age,
                 fmt=MONEY)

    sheet.set("A1", t("Debt and Payments"), TITLE)
    sheet.set("A2", t("What is owed today, by days overdue; the payments collected in the period of the "
                      "filter."), SUBTITLE)
    row = cards(sheet, 4, [("Customers owe us", "Data!B1", None), ("Overdue", "Data!B2", None),
                           ("We owe suppliers", "Data!B3", None), ("To invoice", "Data!B4", None)],
                background="#FFF7ED")
    sheet.figure(scorecard("Collected in the period", "Data!B5", "Data!B6", "vs. the period before",
                           background="#EFF6FF"),
                 col=0, row=row - 1, width=CARD_W, height=CARD_H, y=4)
    sheet.figure(scorecard("Collected today", "Data!B7", background="#EFF6FF"),
                 col=0, row=row - 1, width=CARD_W, height=CARD_H, x=CARD_STEP, y=4)
    chart = native_chart("bar", "Customers' open debt by days overdue", "Data!G2:G6", [("Data!H1:H6", PRIMARY)])
    chart["legendPosition"] = "none"
    sheet.figure(chart, col=0, row=row - 1, width=HALF_W, height=220, x=HALF_STEP, y=4)
    row += rows_for(224)

    row = pivot_table(sheet, row, t("Customers that owe the most, by days overdue"), 2, 15,
                      (MONEY,) * 6, with_columns=True)
    row = pivot_table(sheet, row, t("To invoice to customers"), 3, 10, (MONEY,))
    row = pivot_table(sheet, row, t("Suppliers we owe"), 4, 10, (MONEY,))
    sheet.set("A%s" % row, t("Payments in the period"), SECTION)
    sheet.figure(odoo_chart("odoo_bar", "Payments by day", payment, [], ["date:day"], "amount",
                            matching(payment_chains)),
                 col=0, row=row, width=FULL_W, height=240, y=4)
    row += rows_for(244) + 1
    pivot_table(sheet, row, t("By journal"), 5, 10, (MONEY, INTEGER))
    return book


def main():
    os.makedirs(FILES, exist_ok=True)
    for name, build in (("sales_dashboard", build_sales), ("purchases_dashboard", build_purchases),
                        ("debt_dashboard", build_debt)):
        path = os.path.join(FILES, "%s.json" % name)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(build().data(), file, indent=1, ensure_ascii=False)
            file.write("\n")
        print(path)


if __name__ == "__main__":
    main()
