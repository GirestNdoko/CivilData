from io import BytesIO
from datetime import date

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
)

from src.database import get_connection
from src.costing import get_financial_summary


def get_report_data(start_date, end_date):
    """Récupère les données nécessaires au rapport."""

    with get_connection() as connection:

        production = connection.execute(
            """
            SELECT
                p.product_code,
                p.name,
                p.unit,
                SUM(f.quantity),
                SUM(f.total_cost)
            FROM fabrications f
            JOIN products p ON p.id = f.product_id
            WHERE f.fabrication_date BETWEEN ? AND ?
            GROUP BY p.id, p.product_code, p.name, p.unit
            ORDER BY p.name
            """,
            (start_date, end_date),
        ).fetchall()

        sales = connection.execute(
            """
            SELECT
                p.product_code,
                p.name,
                p.unit,
                SUM(s.quantity),
                SUM(s.quantity * s.unit_price)
            FROM sales s
            JOIN products p ON p.id = s.product_id
            WHERE s.sale_date BETWEEN ? AND ?
            GROUP BY p.id, p.product_code, p.name, p.unit
            ORDER BY p.name
            """,
            (start_date, end_date),
        ).fetchall()

        losses = connection.execute(
            """
            SELECT
                p.product_code,
                p.name,
                p.unit,
                SUM(l.quantity)
            FROM losses l
            JOIN products p ON p.id = l.product_id
            WHERE l.loss_date BETWEEN ? AND ?
            GROUP BY p.id, p.product_code, p.name, p.unit
            ORDER BY p.name
            """,
            (start_date, end_date),
        ).fetchall()

        expenses = connection.execute(
            """
            SELECT
                category,
                SUM(amount)
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY SUM(amount) DESC
            """,
            (start_date, end_date),
        ).fetchall()

    return production, sales, losses, expenses


def create_bar_chart(labels, values, title, ylabel):
    """Crée un diagramme en barres et retourne son image."""

    if not labels or not values:
        return None

    fig, ax = plt.subplots(figsize=(9, 4.5))

    ax.bar(labels, values)

    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=35)

    fig.tight_layout()

    image_buffer = BytesIO()
    fig.savefig(
        image_buffer,
        format="png",
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)
    image_buffer.seek(0)

    return image_buffer


def create_pie_chart(labels, values, title):
    """Crée un diagramme circulaire."""

    if not labels or not values or sum(values) <= 0:
        return None

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
    )

    ax.set_title(title)
    fig.tight_layout()

    image_buffer = BytesIO()
    fig.savefig(
        image_buffer,
        format="png",
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)
    image_buffer.seek(0)

    return image_buffer


def format_number(value):
    """Formate un nombre pour le rapport."""

    return f"{value:,.2f}".replace(",", " ")


def format_fcfa(value):
    """Formate un montant en FCFA."""

    return f"{value:,.0f}".replace(",", " ") + " FCFA"


def make_table(data, widths=None):
    """Construit un tableau PDF avec une présentation uniforme."""

    table = Table(
        data,
        colWidths=widths,
        repeatRows=1,
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#243447"),
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white,
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold",
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.grey,
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#F0F3F5"),
                ],
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
        ])
    )

    return table


def generate_pdf_report(start_date, end_date):
    """Génère un bilan PDF complet pour une période donnée."""

    # Vérification des dates
    try:
        date.fromisoformat(start_date)
        date.fromisoformat(end_date)
    except (ValueError, TypeError):
        raise ValueError("Les dates doivent être au format AAAA-MM-JJ.")

    if start_date > end_date:
        raise ValueError("La date de début doit précéder la date de fin.")

    production, sales, losses, expenses = get_report_data(
        start_date,
        end_date,
    )

    # Indicateurs
    total_production = sum(row[3] or 0 for row in production)
    total_production_cost = sum(row[4] or 0 for row in production)

    total_sales_quantity = sum(row[3] or 0 for row in sales)
    total_revenue = sum(row[4] or 0 for row in sales)

    total_losses = sum(row[3] or 0 for row in losses)
    total_expenses = sum(row[1] or 0 for row in expenses)

    finance = get_financial_summary(start_date, end_date)

    # Construction du PDF en mémoire
    pdf_buffer = BytesIO()

    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Bilan CivilData",
        author="CivilData",
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=21,
            leading=26,
            textColor=colors.HexColor("#243447"),
            spaceAfter=12,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#243447"),
            spaceBefore=14,
            spaceAfter=8,
        )
    )

    story = []

    # PAGE 1 : SYNTHÈSE
    story.append(
        Paragraph("CIVILDATA", styles["ReportTitle"])
    )

    story.append(
        Paragraph(
            "Rapport de fabrication et de gestion des stocks",
            styles["Heading2"],
        )
    )

    story.append(
        Paragraph(
            f"Période : du {start_date} au {end_date}",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 0.5 * cm))

    story.append(
        Paragraph("1. Synthèse générale", styles["SectionTitle"])
    )

    summary_data = [
        ["Indicateur", "Valeur"],
        ["Quantité produite", format_number(total_production)],
        ["Coût total de fabrication", format_fcfa(total_production_cost)],
        ["Quantité vendue", format_number(total_sales_quantity)],
        ["Chiffre d'affaires", format_fcfa(total_revenue)],
        ["Quantité perdue", format_number(total_losses)],
        ["Dépenses générales", format_fcfa(total_expenses)],
        ["Coût des produits vendus (CMP)", format_fcfa(finance["cogs"])],
        ["Marge brute estimée", format_fcfa(finance["gross_margin"])],
        ["Valeur des pertes", format_fcfa(finance["loss_value"])],
        ["Résultat estimé", format_fcfa(finance["estimated_result"])],
        [
            "Valeur du stock de clôture",
            format_fcfa(finance["closing_stock_value"]),
        ],
    ]

    story.append(
        make_table(
            summary_data,
            widths=[9 * cm, 8 * cm],
        )
    )

    story.append(Spacer(1, 0.5 * cm))

    story.append(
        Paragraph(
            "Les quantités sont présentées selon les unités "
            "propres aux produits. Elles ne doivent pas être "
            "additionnées entre produits d'unités différentes.",
            styles["Normal"],
        )
    )

    for warning in finance["warnings"]:
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph("Note : " + warning, styles["Normal"]))

    # PAGE 2 : PRODUCTION
    story.append(PageBreak())

    story.append(
        Paragraph("2. Bilan de production", styles["SectionTitle"])
    )

    production_table = [
        [
            "Code",
            "Produit",
            "Unité",
            "Quantité",
            "Coût (FCFA)",
        ]
    ]

    for row in production:
        production_table.append([
            str(row[0]),
            str(row[1]),
            str(row[2]),
            format_number(row[3] or 0),
            format_fcfa(row[4] or 0),
        ])

    if production:
        story.append(
            make_table(
                production_table,
                widths=[
                    2.3 * cm,
                    4.2 * cm,
                    1.5 * cm,
                    3 * cm,
                    6 * cm,
                ],
            )
        )

        chart = create_bar_chart(
            [row[1] for row in production],
            [row[3] or 0 for row in production],
            "Quantités fabriquées par produit",
            "Quantité",
        )

        if chart:
            story.append(Spacer(1, 0.5 * cm))
            story.append(
                Image(
                    chart,
                    width=16 * cm,
                    height=8 * cm,
                )
            )
    else:
        story.append(
            Paragraph(
                "Aucune fabrication sur cette période.",
                styles["Normal"],
            )
        )

    # PAGE 3 : VENTES
    story.append(PageBreak())

    story.append(
        Paragraph("3. Bilan des ventes", styles["SectionTitle"])
    )

    sales_table = [
        [
            "Code",
            "Produit",
            "Unité",
            "Quantité",
            "Chiffre d'affaires",
        ]
    ]

    for row in sales:
        sales_table.append([
            str(row[0]),
            str(row[1]),
            str(row[2]),
            format_number(row[3] or 0),
            format_fcfa(row[4] or 0),
        ])

    if sales:
        story.append(
            make_table(
                sales_table,
                widths=[
                    2.3 * cm,
                    4.2 * cm,
                    1.5 * cm,
                    3 * cm,
                    6 * cm,
                ],
            )
        )

        chart = create_bar_chart(
            [row[1] for row in sales],
            [row[4] or 0 for row in sales],
            "Chiffre d'affaires par produit",
            "FCFA",
        )

        if chart:
            story.append(Spacer(1, 0.5 * cm))
            story.append(
                Image(
                    chart,
                    width=16 * cm,
                    height=8 * cm,
                )
            )
    else:
        story.append(
            Paragraph(
                "Aucune vente sur cette période.",
                styles["Normal"],
            )
        )

    # PAGE 4 : PERTES
    story.append(PageBreak())

    story.append(
        Paragraph("4. Bilan des pertes", styles["SectionTitle"])
    )

    losses_table = [
        ["Code", "Produit", "Unité", "Quantité perdue"]
    ]

    for row in losses:
        losses_table.append([
            str(row[0]),
            str(row[1]),
            str(row[2]),
            format_number(row[3] or 0),
        ])

    if losses:
        story.append(
            make_table(
                losses_table,
                widths=[
                    3 * cm,
                    6 * cm,
                    3 * cm,
                    5 * cm,
                ],
            )
        )

        chart = create_bar_chart(
            [row[1] for row in losses],
            [row[3] or 0 for row in losses],
            "Quantités perdues par produit",
            "Quantité",
        )

        if chart:
            story.append(Spacer(1, 0.5 * cm))
            story.append(
                Image(
                    chart,
                    width=16 * cm,
                    height=8 * cm,
                )
            )
    else:
        story.append(
            Paragraph(
                "Aucune perte sur cette période.",
                styles["Normal"],
            )
        )

    # PAGE 5 : DÉPENSES
    story.append(PageBreak())

    story.append(
        Paragraph("5. Bilan des dépenses générales", styles["SectionTitle"])
    )

    expenses_table = [
        ["Catégorie", "Montant (FCFA)"]
    ]

    for row in expenses:
        expenses_table.append([
            str(row[0]),
            format_fcfa(row[1] or 0),
        ])

    if expenses:
        story.append(
            make_table(
                expenses_table,
                widths=[8 * cm, 9 * cm],
            )
        )

        chart = create_pie_chart(
            [row[0] for row in expenses],
            [row[1] or 0 for row in expenses],
            "Répartition des dépenses",
        )

        if chart:
            story.append(Spacer(1, 0.5 * cm))
            story.append(
                Image(
                    chart,
                    width=14 * cm,
                    height=10 * cm,
                )
            )
    else:
        story.append(
            Paragraph(
                "Aucune dépense sur cette période.",
                styles["Normal"],
            )
        )

    # Pied de page
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(
            A4[0] / 2,
            0.8 * cm,
            f"CivilData - Page {doc.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    pdf_buffer.seek(0)

    return pdf_buffer.getvalue()