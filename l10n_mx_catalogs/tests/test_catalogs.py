from odoo.addons.base.tests.common import BaseCommon

CATALOG_MODELS = [
    "l10n_mx_catalogs.c_clave_prod_serv",
    "l10n_mx_catalogs.c_clave_unidad",
    "l10n_mx_catalogs.c_codigo_postal",
    "l10n_mx_catalogs.c_colonia",
    "l10n_mx_catalogs.c_config_autotransporte",
    "l10n_mx_catalogs.c_figura_transporte",
    "l10n_mx_catalogs.c_forma_pago",
    "l10n_mx_catalogs.c_localidad",
    "l10n_mx_catalogs.c_meses",
    "l10n_mx_catalogs.c_metodo_pago",
    "l10n_mx_catalogs.c_motivo_cancelacion",
    "l10n_mx_catalogs.c_pais",
    "l10n_mx_catalogs.c_parte_transporte",
    "l10n_mx_catalogs.c_periodicidad",
    "l10n_mx_catalogs.c_regimen_fiscal",
    "l10n_mx_catalogs.c_sub_tipo_rem",
    "l10n_mx_catalogs.c_tipo_permiso",
    "l10n_mx_catalogs.c_tipo_relacion",
    "l10n_mx_catalogs.c_uso_cfdi",
]


class TestCatalogs(BaseCommon):
    def test_every_catalog_ships_data(self):
        for model in CATALOG_MODELS:
            with self.subTest(model=model):
                self.assertTrue(
                    self.env[model].search_count([]),
                    f"El catálogo {model} se instala vacío",
                )

    def test_display_name_shows_code_and_name(self):
        efectivo = self.env.ref("l10n_mx_catalogs.c_forma_pago_01")
        self.assertIn("[01]", efectivo.display_name)
        self.assertIn(efectivo.name, efectivo.display_name)

    def test_name_search_by_code(self):
        efectivo = self.env.ref("l10n_mx_catalogs.c_forma_pago_01")
        found = self.env["l10n_mx_catalogs.c_forma_pago"].name_search("01")
        self.assertIn(efectivo.id, [rec_id for rec_id, _name in found])

    def test_name_search_by_name(self):
        efectivo = self.env.ref("l10n_mx_catalogs.c_forma_pago_01")
        found = self.env["l10n_mx_catalogs.c_forma_pago"].name_search("Efectivo")
        self.assertIn(efectivo.id, [rec_id for rec_id, _name in found])

    def test_regimen_fiscal_applicability_flags(self):
        general_ley = self.env.ref("l10n_mx_catalogs.c_regimen_fiscal_601")
        self.assertTrue(general_ley.applies_to_legal_person)
        self.assertFalse(general_ley.applies_to_natural_person)
