import streamlit as st
import pandas as pd
import plotly.express as px

from datetime import date
from src.database import get_connection, reset_all_data
from src.init_db import (
    create_products_table,
    add_product,
    get_products,
    update_product,
    deactivate_product,
)
from src.fabrication import create_fabrications_table, add_fabrication, get_fabrications
from src.sales import create_sales_table, add_sale, get_sales
from src.losses import create_losses_table, add_loss, get_losses
from src.stock import (
    create_stock_tables,
    set_opening_stock,
    get_stock_summary,
    register_inventory_count,
)
from src.expenses import create_expenses_table, add_expense, get_expenses
from src.reports import get_period_report
from src.analytics import (
    get_production_summary,
    get_sales_summary,
    get_losses_summary,
    get_expenses_summary,
)
from src.forecast import get_forecast_summary
from src.costing import get_financial_summary
from src.corrections import (
    create_audit_table,
    correct_operation,
    get_audit_log,
    EDITABLE,
)
from src.backup import (
    create_backup,
    list_backups,
    restore_backup,
)
from src.pdf_reports import generate_pdf_report
from src.auth import require_password
from src.demo import (
    first_run_setup,
    is_demo_active,
    clear_demo_data,
    load_demo_data,
    database_is_empty,
)


# Initialisation automatique des tables
def initialize_app():
    create_products_table()
    create_fabrications_table()
    create_sales_table()
    create_losses_table()
    create_stock_tables()
    create_expenses_table()
    create_audit_table()


st.set_page_config(
    page_title="CivilData",
    page_icon="🏗️",
    layout="wide",
)

require_password()  # mot de passe si APP_PASSWORD est défini

initialize_app()
first_run_setup()  # charge la démo au tout premier lancement

st.title("🏗️ CivilData")
st.caption("Gestion de fabrication, de stocks et de résultats")

if is_demo_active():
    banner, action = st.columns([4, 1])
    banner.info(
        "🧪 **Mode démo** : vous consultez douze mois de données fictives. "
        "Explorez l'application, puis supprimez la démo pour saisir "
        "vos propres données."
    )
    if action.button("Supprimer la démo", type="primary"):
        st.session_state["confirm_demo_delete"] = True

    if st.session_state.get("confirm_demo_delete"):
        st.warning(
            "Toutes les données actuelles seront effacées "
            "(démo et éventuelles saisies de votre part)."
        )
        yes, no = st.columns(2)
        if yes.button("Oui, tout supprimer"):
            clear_demo_data()
            st.session_state.pop("confirm_demo_delete", None)
            st.session_state.pop("rapport_pdf", None)
            st.rerun()
        if no.button("Annuler"):
            st.session_state.pop("confirm_demo_delete", None)
            st.rerun()


# Données communes
def load_products(active_only=False):
    products = get_products()
    if active_only:
        products = [p for p in products if p[5] == 1]
    return products


def product_label(product):
    return f"{product[1]} — {product[2]} ({product[4]})"


def product_selector(label="Produit"):
    products = load_products(active_only=True)

    if not products:
        st.warning("Crée d'abord un produit dans la rubrique Produits.")
        return None

    return st.selectbox(
        label,
        products,
        format_func=product_label,
        key=label,
    )


def operation_date(label):
    return st.date_input(label, value=date.today())


# Navigation
page = st.sidebar.radio(
    "Navigation",
    [
        "Tableau de bord",
        "Produits",
        "Fabrications",
        "Ventes",
        "Pertes",
        "Stocks et inventaires",
        "Dépenses",
        "Bilans",
        "Historique",
        "Corrections",
        "Analyses",
        "Prévisions",
        "Rapports PDF",
        "Paramètres",
    ],
)


# TABLEAU DE BORD
if page == "Tableau de bord":
    st.subheader("Vue d'ensemble")

    products = load_products(active_only=True)
    stock = get_stock_summary()

    col1, col2 = st.columns(2)
    col1.metric("Produits actifs", len(products))
    col2.metric("Produits référencés en stock", len(stock))

    st.info(
        "Pour obtenir des stocks fiables, renseigne le stock initial "
        "de chaque produit avant d'interpréter les quantités calculées."
    )

    st.subheader("Situation actuelle des stocks")

    if stock:
        st.dataframe(
            [
                {
                    "Code": row[0],
                    "Produit": row[1],
                    "Unité": row[2],
                    "Stock calculé": row[3],
                    "Statut": "Actif" if row[4] == 1 else "Inactif",
                }
                for row in stock
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("Aucun produit enregistré.")


# PRODUITS
elif page == "Produits":
    st.subheader("Gestion des produits")

    with st.form("new_product"):
        st.markdown("#### Ajouter un produit")
        name = st.text_input("Nom du produit")
        category = st.text_input("Catégorie")
        unit = st.selectbox(
            "Unité de mesure",
            ["pièce", "sac", "kg", "tonne", "m³", "litre", "autre"],
        )
        submitted = st.form_submit_button("Enregistrer le produit")

        if submitted:
            try:
                code = add_product(name, category, unit)
                st.success(f"Produit enregistré : {code}")
                st.rerun()
            except (ValueError, Exception) as error:
                st.error(f"Impossible d'enregistrer le produit : {error}")

    st.divider()
    st.markdown("#### Produits existants")

    products = load_products()
    if products:
        st.dataframe(
            [
                {
                    "Code": p[1],
                    "Nom": p[2],
                    "Catégorie": p[3],
                    "Unité": p[4],
                    "Statut": "Actif" if p[5] == 1 else "Inactif",
                }
                for p in products
            ],
            use_container_width=True,
            hide_index=True,
        )

        editable = st.selectbox(
            "Produit à modifier",
            products,
            format_func=product_label,
        )

        if editable[5] == 1:
            with st.form("edit_product"):
                new_name = st.text_input("Nom", value=editable[2])
                new_category = st.text_input(
                    "Catégorie", value=editable[3]
                )
                units = ["pièce", "sac", "kg", "tonne", "m³", "litre", "autre"]
                if editable[4] not in units:
                    units.append(editable[4])
                new_unit = st.selectbox(
                    "Unité", units, index=units.index(editable[4])
                )

                update = st.form_submit_button("Enregistrer les modifications")

                if update:
                    try:
                        ok = update_product(
                            editable[0],
                            new_name,
                            new_category,
                            new_unit,
                        )
                        if ok:
                            st.success("Produit modifié.")
                            st.rerun()
                        else:
                            st.error("Modification impossible.")
                    except Exception as error:
                        st.error(str(error))

            if st.button("Désactiver ce produit"):
                if deactivate_product(editable[0]):
                    st.success("Produit désactivé. Son historique est conservé.")
                    st.rerun()
                else:
                    st.warning("Ce produit est déjà inactif.")
    else:
        st.write("Aucun produit pour le moment.")


# FABRICATIONS
elif page == "Fabrications":
    st.subheader("Enregistrer une fabrication")
    product = product_selector()

    if product:
        with st.form("fabrication_form"):
            d = operation_date("Date de fabrication")
            quantity = st.number_input(
                "Quantité fabriquée", min_value=0.001, value=1.0
            )
            cost = st.number_input(
                "Coût total de fabrication (FCFA)",
                min_value=0.0,
                value=0.0,
            )
            notes = st.text_area("Observations")
            submit = st.form_submit_button("Enregistrer")

            if submit:
                try:
                    add_fabrication(
                        product[0], d.isoformat(), quantity, cost, notes
                    )
                    st.success("Fabrication enregistrée.")
                    st.rerun()
                except Exception as error:
                    st.error(str(error))


# VENTES
elif page == "Ventes":
    st.subheader("Enregistrer une vente")
    product = product_selector()

    if product:
        with st.form("sale_form"):
            d = operation_date("Date de vente")
            quantity = st.number_input(
                "Quantité vendue", min_value=0.001, value=1.0
            )
            price = st.number_input(
                "Prix de vente unitaire (FCFA)",
                min_value=0.0,
                value=0.0,
            )
            notes = st.text_area("Observations")
            submit = st.form_submit_button("Enregistrer la vente")

            if submit:
                try:
                    add_sale(
                        product[0], d.isoformat(), quantity, price, notes
                    )
                    st.success(
                        f"Vente enregistrée. Montant : "
                        f"{quantity * price:,.0f} FCFA"
                    )
                except Exception as error:
                    st.error(str(error))


# PERTES
elif page == "Pertes":
    st.subheader("Enregistrer une perte")
    product = product_selector()

    if product:
        with st.form("loss_form"):
            d = operation_date("Date de la perte")
            quantity = st.number_input(
                "Quantité perdue", min_value=0.001, value=1.0
            )
            reason = st.text_input(
                "Motif", placeholder="Casse, défaut, détérioration..."
            )
            notes = st.text_area("Observations")
            submit = st.form_submit_button("Enregistrer la perte")

            if submit:
                try:
                    add_loss(
                        product[0],
                        d.isoformat(),
                        quantity,
                        reason,
                        notes,
                    )
                    st.success("Perte enregistrée.")
                except Exception as error:
                    st.error(str(error))


# STOCKS ET INVENTAIRES
elif page == "Stocks et inventaires":
    st.subheader("Stocks et inventaires")

    product = product_selector("Produit pour le stock initial")

    if product:
        with st.form("opening_stock_form"):
            d = operation_date("Date de référence du stock initial")
            quantity = st.number_input(
                "Quantité disponible à cette date",
                min_value=0.0,
                value=0.0,
            )
            submit = st.form_submit_button("Définir le stock initial")

            if submit:
                try:
                    set_opening_stock(
                        product[0], d.isoformat(), quantity
                    )
                    st.success("Stock initial enregistré.")
                except Exception as error:
                    st.error(
                        f"Impossible d'enregistrer le stock initial : {error}"
                    )

    st.divider()
    st.markdown("#### Inventaire physique")

    product = product_selector("Produit à inventorier")

    if product:
        with st.form("inventory_form"):
            d = operation_date("Date de l'inventaire")
            physical = st.number_input(
                "Quantité réellement comptée",
                min_value=0.0,
                value=0.0,
            )
            notes = st.text_area("Commentaire sur l'écart éventuel")
            submit = st.form_submit_button("Valider l'inventaire")

            if submit:
                try:
                    theoretical, actual, delta = register_inventory_count(
                        product[0], d.isoformat(), physical, notes
                    )
                    st.write(f"Stock théorique : {theoretical}")
                    st.write(f"Stock physique : {actual}")
                    st.write(f"Écart constaté : {delta}")
                    st.success("Inventaire enregistré.")
                except Exception as error:
                    st.error(str(error))

    st.divider()
    st.markdown("#### État des stocks")

    as_of = operation_date("Stock calculé à la date du")
    stock = get_stock_summary(as_of.isoformat())

    # Un produit sans stock initial ne doit pas être interprété
    # comme ayant réellement zéro stock.
    with get_connection() as connection:
        openings = {
            row[0]
            for row in connection.execute(
                "SELECT product_id FROM stock_openings"
            ).fetchall()
        }
        all_products = connection.execute(
            "SELECT id, product_code, name, unit, is_active FROM products"
        ).fetchall()

    missing = [p for p in all_products if p[0] not in openings]
    if missing:
        st.warning(
            f"{len(missing)} produit(s) sans stock initial : "
            + ", ".join(p[2] for p in missing)
            + ". Leur stock calculé n'est pas fiable."
        )

    st.dataframe(
        [
            {
                "Code": row[0],
                "Produit": row[1],
                "Unité": row[2],
                "Stock calculé": row[3],
                "Statut": "Actif" if row[4] == 1 else "Inactif",
            }
            for row in stock
        ],
        use_container_width=True,
        hide_index=True,
    )


# DEPENSES
elif page == "Dépenses":
    st.subheader("Enregistrer une dépense")

    with st.form("expense_form"):
        d = operation_date("Date de la dépense")
        category = st.selectbox(
            "Catégorie",
            [
                "Matières premières",
                "Énergie",
                "Transport",
                "Entretien",
                "Salaires",
                "Loyer",
                "Autre",
            ],
        )
        description = st.text_input("Description")
        amount = st.number_input(
            "Montant (FCFA)", min_value=0.01, value=100.0
        )
        notes = st.text_area("Observations")
        submit = st.form_submit_button("Enregistrer la dépense")

        if submit:
            try:
                add_expense(
                    d.isoformat(), category, description, amount, notes
                )
                st.success("Dépense enregistrée.")
            except Exception as error:
                st.error(str(error))


# BILANS
elif page == "Bilans":
    st.subheader("Bilan d'une période")

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input(
            "Début de période", value=date(date.today().year, 1, 1)
        )
    with col2:
        end = st.date_input("Fin de période", value=date.today())

    if st.button("Calculer le bilan"):
        try:
            report = get_period_report(
                start.isoformat(), end.isoformat()
            )

            if start > end:
                st.error("La date de début doit précéder la date de fin.")
            else:
                c1, c2, c3 = st.columns(3)
                c1.metric(
                    "Coût de fabrication",
                    f"{report['total_production_cost']:,.0f} FCFA",
                )
                c2.metric(
                    "Chiffre d'affaires",
                    f"{report['total_sales_revenue']:,.0f} FCFA",
                )
                c3.metric(
                    "Dépenses générales",
                    f"{report['total_general_expenses']:,.0f} FCFA",
                )

                finance = get_financial_summary(
                    start.isoformat(), end.isoformat()
                )

                st.markdown("#### Résultat estimé (coût moyen pondéré)")
                f1, f2, f3 = st.columns(3)
                f1.metric(
                    "Coût des produits vendus",
                    f"{finance['cogs']:,.0f} FCFA",
                )
                f2.metric(
                    "Marge brute",
                    f"{finance['gross_margin']:,.0f} FCFA",
                    (
                        f"{finance['gross_margin_rate']:.1%}"
                        if finance["gross_margin_rate"] is not None
                        else None
                    ),
                )
                f3.metric(
                    "Résultat estimé",
                    f"{finance['estimated_result']:,.0f} FCFA",
                )
                f4, f5 = st.columns(2)
                f4.metric(
                    "Valeur des pertes",
                    f"{finance['loss_value']:,.0f} FCFA",
                )
                f5.metric(
                    "Valeur du stock de clôture",
                    f"{finance['closing_stock_value']:,.0f} FCFA",
                )
                for warning in finance["warnings"]:
                    st.caption("⚠️ " + warning)

                st.markdown("#### Détail par produit")
                st.dataframe(
                    [
                        {
                            "Code": p["product_code"],
                            "Produit": p["name"],
                            "Unité": p["unit"],
                            "Quantité fabriquée": p["quantity_produced"],
                            "Coût fabrication (FCFA)": p["production_cost"],
                            "Quantité vendue": p["quantity_sold"],
                            "Ventes (FCFA)": p["sales_revenue"],
                            "Quantité perdue": p["quantity_lost"],
                        }
                        for p in report["products"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        except Exception as error:
            st.error(f"Erreur lors du calcul du bilan : {error}")

#Historique
elif page == "Historique":
    st.subheader("Historique des opérations")

    # Choix de la période
    st.markdown("### Filtrer par période")

    col1, col2 = st.columns(2)

    with col1:
        debut = st.date_input(
            "Date de début",
            value=date.today().replace(day=1),
            key="historique_debut",
        )

    with col2:
        fin = st.date_input(
            "Date de fin",
            value=date.today(),
            key="historique_fin",
        )

    if debut > fin:
        st.error(
            "La date de début doit être antérieure "
            "ou égale à la date de fin."
        )

    else:
        debut_str = debut.isoformat()
        fin_str = fin.isoformat()

        # Choix de la catégorie
        categorie = st.selectbox(
            "Type d'opération à consulter",
            [
                "Toutes les opérations",
                "Fabrications",
                "Ventes",
                "Pertes",
                "Dépenses",
            ],
        )

        # Récupération des données
        fabrications = []
        ventes = []
        pertes = []
        depenses = []

        if categorie in ["Toutes les opérations", "Fabrications"]:
            fabrications = get_fabrications(debut_str, fin_str)

        if categorie in ["Toutes les opérations", "Ventes"]:
            ventes = get_sales(debut_str, fin_str)

        if categorie in ["Toutes les opérations", "Pertes"]:
            pertes = get_losses(debut_str, fin_str)

        if categorie in ["Toutes les opérations", "Dépenses"]:
            depenses = get_expenses(debut_str, fin_str)

        # Affichage des fabrications
        if categorie in ["Toutes les opérations", "Fabrications"]:
            st.markdown("### Fabrications")

            if fabrications:
                colonnes = [
                    "ID",
                    "Date",
                    "Code produit",
                    "Produit",
                    "Unité",
                    "Quantité fabriquée",
                    "Coût total (FCFA)",
                    "Observations",
                ]

                st.dataframe(
                    [
                        dict(zip(colonnes, ligne))
                        for ligne in fabrications
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                quantite_totale = sum(
                    ligne[5] for ligne in fabrications
                )
                cout_total = sum(
                    ligne[6] for ligne in fabrications
                )

                col1, col2 = st.columns(2)

                col1.metric(
                    "Quantité totale fabriquée",
                    f"{quantite_totale:,.2f}",
                )

                col2.metric(
                    "Coût total de fabrication",
                    f"{cout_total:,.0f} FCFA",
                )

            else:
                st.info("Aucune fabrication sur cette période.")

        # Affichage des ventes
        if categorie in ["Toutes les opérations", "Ventes"]:
            st.markdown("### Ventes")

            if ventes:
                colonnes = [
                    "ID",
                    "Date",
                    "Code produit",
                    "Produit",
                    "Unité",
                    "Quantité vendue",
                    "Prix unitaire (FCFA)",
                    "Montant total (FCFA)",
                    "Observations",
                ]

                st.dataframe(
                    [
                        dict(zip(colonnes, ligne))
                        for ligne in ventes
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                quantite_vendue = sum(
                    ligne[5] for ligne in ventes
                )
                montant_ventes = sum(
                    ligne[7] for ligne in ventes
                )

                col1, col2 = st.columns(2)

                col1.metric(
                    "Quantité totale vendue",
                    f"{quantite_vendue:,.2f}",
                )

                col2.metric(
                    "Montant total des ventes",
                    f"{montant_ventes:,.0f} FCFA",
                )

            else:
                st.info("Aucune vente sur cette période.")

        # Affichage des pertes
        if categorie in ["Toutes les opérations", "Pertes"]:
            st.markdown("### Pertes")

            if pertes:
                colonnes = [
                    "ID",
                    "Date",
                    "Code produit",
                    "Produit",
                    "Unité",
                    "Quantité perdue",
                    "Motif",
                    "Observations",
                ]

                st.dataframe(
                    [
                        dict(zip(colonnes, ligne))
                        for ligne in pertes
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                quantite_perdue = sum(
                    ligne[5] for ligne in pertes
                )

                st.metric(
                    "Quantité totale perdue",
                    f"{quantite_perdue:,.2f}",
                )

            else:
                st.info("Aucune perte sur cette période.")

        # Affichage des dépenses
        if categorie in ["Toutes les opérations", "Dépenses"]:
            st.markdown("### Dépenses")

            if depenses:
                colonnes = [
                    "ID",
                    "Date",
                    "Catégorie",
                    "Description",
                    "Montant (FCFA)",
                    "Observations",
                ]

                st.dataframe(
                    [
                        dict(zip(colonnes, ligne))
                        for ligne in depenses
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                montant_depenses = sum(
                    ligne[4] for ligne in depenses
                )

                st.metric(
                    "Montant total des dépenses",
                    f"{montant_depenses:,.0f} FCFA",
                )

            else:
                st.info("Aucune dépense sur cette période.")

#Parametres
elif page == "Paramètres":
    st.subheader("Réinitialiser CivilData")

    st.warning(
        "Cette action supprimera toutes les données enregistrées, "
        "y compris les produits. Cette opération est irréversible."
    )

    confirmation = st.checkbox(
        "Je confirme vouloir supprimer toutes les données."
    )

    if st.button(
        "Réinitialiser toutes les données",
        type="primary",
        disabled=not confirmation,
    ):
        try:
            clear_demo_data()  # réinitialise aussi le mode démo
            st.success("Toutes les données ont été supprimées.")
            st.rerun()
        except Exception as error:
            st.error(f"Erreur : {error}")

    st.divider()
    st.subheader("Sauvegarde et restauration")

    if st.button("Créer une sauvegarde maintenant"):
        path = create_backup()
        st.success(f"Sauvegarde créée : {path.name}")

    backups = list_backups()
    if backups:
        chosen = st.selectbox(
            "Sauvegardes disponibles", backups, format_func=lambda p: p.name
        )
        st.download_button(
            "Télécharger cette sauvegarde",
            data=chosen.read_bytes(),
            file_name=chosen.name,
            mime="application/octet-stream",
        )
        if st.checkbox("Je confirme remplacer les données par cette sauvegarde"):
            if st.button("Restaurer la sauvegarde choisie"):
                try:
                    safety = restore_backup(chosen)
                    st.success(
                        "Sauvegarde restaurée. L'état précédent est conservé "
                        f"dans {safety.name}."
                    )
                    st.rerun()
                except Exception as error:
                    st.error(str(error))
    else:
        st.caption("Aucune sauvegarde pour le moment.")

    st.divider()
    st.subheader("Données de démonstration")
    if database_is_empty():
        st.write("La base est vide. Vous pouvez recharger la démo.")
        if st.button("Charger les données de démo"):
            load_demo_data()
            st.rerun()
    else:
        st.caption(
            "La démo ne peut être rechargée que lorsque la base est vide."
        )

# CORRECTIONS
elif page == "Corrections":
    st.subheader("Corriger une opération")
    st.caption(
        "Aucune opération n'est supprimée : chaque correction est contrôlée "
        "et conservée dans le journal des modifications."
    )

    labels = {
        "fabrications": "Fabrication",
        "sales": "Vente",
        "losses": "Perte",
        "expenses": "Dépense",
    }
    table = st.selectbox(
        "Type d'opération", list(labels), format_func=labels.get
    )
    fetchers = {
        "fabrications": get_fabrications,
        "sales": get_sales,
        "losses": get_losses,
        "expenses": get_expenses,
    }
    rows = fetchers[table]()

    if not rows:
        st.info("Aucune opération de ce type.")
    else:
        st.dataframe(
            [dict(zip(range(len(r)), r)) for r in rows[:100]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Les 100 opérations les plus récentes (colonne 0 = ID).")

        op_id = st.number_input("ID de l'opération", min_value=1, step=1)
        _, fields = EDITABLE[table]
        field = st.selectbox(
            "Champ à corriger",
            [f for f in fields if f != "notes"],
        )
        kind = fields[field]
        if kind == "date":
            value = st.date_input("Nouvelle date").isoformat()
        elif kind in ("positive", "non_negative"):
            value = st.number_input("Nouvelle valeur", value=1.0)
        else:
            value = st.text_input("Nouvelle valeur")
        reason = st.text_input("Motif de la correction (obligatoire)")

        if st.button("Appliquer la correction"):
            try:
                changed = correct_operation(
                    table, int(op_id), {field: value}, reason
                )
                st.success(f"Correction enregistrée : {', '.join(changed)}.")
            except Exception as error:
                st.error(str(error))

    st.divider()
    st.markdown("#### Journal des modifications")
    log = get_audit_log()
    if log:
        st.dataframe(
            [
                dict(zip(
                    ["Date", "Table", "ID", "Champ",
                     "Ancienne valeur", "Nouvelle valeur", "Motif"],
                    row,
                ))
                for row in log
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("Aucune correction enregistrée.")

#Analyses
elif page == "Analyses":
    st.subheader("Analyses statistiques")
    st.write(
        "Analyse de la production, des ventes, "
        "des pertes et des dépenses."
    )

    col1, col2 = st.columns(2)

    with col1:
        debut = st.date_input(
            "Date de début",
            value=date.today().replace(day=1),
            key="analyse_debut",
        )

    with col2:
        fin = st.date_input(
            "Date de fin",
            value=date.today(),
            key="analyse_fin",
        )

    if debut > fin:
        st.error("La date de début doit précéder la date de fin.")

    else:
        debut = debut.isoformat()
        fin = fin.isoformat()

        productions = get_production_summary(debut, fin)
        ventes = get_sales_summary(debut, fin)
        pertes = get_losses_summary(debut, fin)
        depenses = get_expenses_summary(debut, fin)

        # INDICATEURS GÉNÉRAUX
        quantite_produite = sum(
            ligne[3] or 0 for ligne in productions
        )
        cout_production = sum(
            ligne[4] or 0 for ligne in productions
        )
        chiffre_affaires = sum(
            ligne[4] or 0 for ligne in ventes
        )
        quantite_perdue = sum(
            ligne[3] or 0 for ligne in pertes
        )
        total_depenses = sum(
            ligne[1] or 0 for ligne in depenses
        )

        st.markdown("### Indicateurs clés")

        c1, c2 = st.columns(2)
        c1.metric(
            "Coût de production",
            f"{cout_production:,.0f} FCFA",
        )
        c2.metric(
            "Chiffre d'affaires",
            f"{chiffre_affaires:,.0f} FCFA",
        )

        c3, c4 = st.columns(2)
        c3.metric(
            "Dépenses générales",
            f"{total_depenses:,.0f} FCFA",
        )
        c4.metric(
            "Quantité totale perdue",
            f"{quantite_perdue:,.2f}",
        )

        st.caption(
            f"Quantité produite : {quantite_produite:,.2f}. "
            "Les quantités de produits d'unités différentes "
            "ne sont pas directement comparables."
        )

        # ANALYSE DE LA PRODUCTION
        st.markdown("### Production")

        if productions:
            df = pd.DataFrame(
                productions,
                columns=[
                    "Code produit",
                    "Produit",
                    "Unité",
                    "Quantité produite",
                    "Coût total",
                ],
            )

            st.dataframe(df, use_container_width=True)

            fig = px.bar(
                df,
                x="Produit",
                y="Quantité produite",
                color="Produit",
                title="Quantités fabriquées par produit",
                hover_data=["Code produit", "Unité"],
            )
            st.plotly_chart(fig, use_container_width=True)

            fig = px.bar(
                df,
                x="Produit",
                y="Coût total",
                title="Coût de fabrication par produit",
                hover_data=["Code produit"],
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune fabrication pour cette période.")

        # ANALYSE DES VENTES
        st.markdown("### Ventes")

        if ventes:
            df = pd.DataFrame(
                ventes,
                columns=[
                    "Code produit",
                    "Produit",
                    "Unité",
                    "Quantité vendue",
                    "Chiffre d'affaires",
                ],
            )

            st.dataframe(df, use_container_width=True)

            fig = px.bar(
                df,
                x="Produit",
                y="Chiffre d'affaires",
                title="Chiffre d'affaires par produit",
                hover_data=["Code produit"],
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune vente pour cette période.")

        # ANALYSE DES PERTES
        st.markdown("### Pertes")

        if pertes:
            df = pd.DataFrame(
                pertes,
                columns=[
                    "Code produit",
                    "Produit",
                    "Unité",
                    "Quantité perdue",
                ],
            )

            st.dataframe(df, use_container_width=True)

            fig = px.bar(
                df,
                x="Produit",
                y="Quantité perdue",
                title="Pertes par produit",
                hover_data=["Code produit", "Unité"],
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune perte pour cette période.")

        # ANALYSE DES DÉPENSES
        st.markdown("### Dépenses générales")

        if depenses:
            df = pd.DataFrame(
                depenses,
                columns=["Catégorie", "Montant"],
            )

            st.dataframe(df, use_container_width=True)

            fig = px.pie(
                df,
                names="Catégorie",
                values="Montant",
                title="Répartition des dépenses",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune dépense pour cette période.")
#Prévisions
elif page == "Prévisions":
    st.subheader("Prévisions de fabrication")

    st.write(
        "Estimez l'autonomie des stocks et anticipez "
        "les risques de rupture à partir des ventes récentes."
    )

    col1, col2 = st.columns(2)

    with col1:
        periode = st.selectbox(
            "Période d'analyse des ventes",
            [7, 14, 30, 60, 90],
            index=2,
            format_func=lambda jours: f"{jours} derniers jours",
        )

    with col2:
        date_observation = st.date_input(
            "Date d'observation",
            value=date.today(),
            key="forecast_date",
        )

    if st.button("Calculer les prévisions"):
        try:
            resultats = get_forecast_summary(
                history_days=periode,
                as_of_date=date_observation,
            )

            if not resultats:
                st.info(
                    "Aucun produit actif à analyser."
                )

            else:
                df = pd.DataFrame(resultats)

                st.markdown("### Résultats")

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                )

                urgents = sum(
                    ligne["Alerte"] in [
                        "Rupture ou stock nul",
                        "Fabrication urgente",
                    ]
                    for ligne in resultats
                )

                a_prevoir = sum(
                    ligne["Alerte"] == "Fabrication à prévoir"
                    for ligne in resultats
                )

                col1, col2 = st.columns(2)

                col1.metric(
                    "Produits nécessitant une attention urgente",
                    urgents,
                )

                col2.metric(
                    "Fabrications à prévoir",
                    a_prevoir,
                )

                st.markdown("### Autonomie des stocks")

                df_graphique = df[
                    df["Autonomie estimée (jours)"].notna()
                ].copy()

                if not df_graphique.empty:
                    fig = px.bar(
                        df_graphique,
                        x="Produit",
                        y="Autonomie estimée (jours)",
                        color="Alerte",
                        hover_data=[
                            "Code produit",
                            "Stock actuel",
                            "Ventes moyennes par jour",
                        ],
                        title="Autonomie estimée par produit",
                    )

                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                    )

                st.caption(
                    "Les prévisions supposent un rythme de ventes "
                    "constant. Elles ne tiennent pas encore compte "
                    "des commandes futures, de la saisonnalité, "
                    "des délais de fabrication ou des contraintes "
                    "de capacité de l'usine."
                )

        except (ValueError, TypeError) as erreur:
            st.error(f"Erreur de calcul : {erreur}")
#Rapports PDF
elif page == "Rapports PDF":
    st.subheader("Génération des bilans PDF")

    st.write(
        "Générez un rapport complet comprenant les indicateurs, "
        "les tableaux et les graphiques de la période choisie."
    )

    col1, col2 = st.columns(2)

    with col1:
        debut_rapport = st.date_input(
            "Date de début du rapport",
            value=date.today().replace(day=1),
            key="pdf_debut",
        )

    with col2:
        fin_rapport = st.date_input(
            "Date de fin du rapport",
            value=date.today(),
            key="pdf_fin",
        )

    if debut_rapport > fin_rapport:
        st.error(
            "La date de début doit précéder la date de fin."
        )

    else:
        if st.button("Générer le rapport PDF"):
            try:
                contenu_pdf = generate_pdf_report(
                    debut_rapport.isoformat(),
                    fin_rapport.isoformat(),
                )

                st.session_state["rapport_pdf"] = contenu_pdf

                st.success("Le rapport PDF a été généré.")

            except Exception as erreur:
                st.error(
                    f"Impossible de générer le rapport : {erreur}"
                )

        if st.session_state.get("rapport_pdf"):
            st.download_button(
                label="Télécharger le bilan PDF",
                data=st.session_state["rapport_pdf"],
                file_name=(
                    f"CivilData_bilan_"
                    f"{debut_rapport.isoformat()}_"
                    f"{fin_rapport.isoformat()}.pdf"
                ),
                mime="application/pdf",
            )