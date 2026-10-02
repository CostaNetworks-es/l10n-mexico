import json
from base64 import b64encode

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

CFDI_NOTE = "Este documento es una representación impresa de un CFDI"
STAMPED_CFDI_JSON = json.dumps(
    {
        "Date": "2026-10-02T10:00:00",
        "CertNumber": "30001000000400002434",
        "OriginalString": "||4.0|TST|1||",
        "Total": 100.0,
        "Complement": {
            "TaxStamp": {
                "CfdiSign": "A" * 40,
                "SatSign": "B" * 40,
                "SatCertNumber": "30001000000500003456",
                "RfcProvCertif": "SPR190613I52",
                "Date": "2026-10-02T10:00:05",
            }
        },
    }
)


@tagged("post_install", "-at_install")
class TestCFDIReports(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("mx")
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["l10n_mx_cfdi.cfdi_service"].create(
            {"name": "Test service", "user": "test_user", "password": "test_password"}
        )
        cls.regimen = cls.env.ref("l10n_mx_catalogs.c_regimen_fiscal_601")
        cls.partner_a.write({"vat": "XEXX010101000", "tax_regime": cls.regimen.id})
        cls.issuer = cls.env["l10n_mx_cfdi.issuer"].create(
            {
                "name": "Test Issuer",
                "vat": "RFC123456",
                "zip": "77500",
                "tax_regime": cls.regimen.id,
                "certificate_file": b64encode(b"certificate"),
                "key_file": b64encode(b"key"),
                "key_password": "password",
                "service_id": cls.service.id,
            }
        )
        cls.invoice = cls.init_invoice(
            "out_invoice", products=cls.product_a, amounts=[100.0]
        )
        # Posted without a CFDI: the stamp is simulated by each test
        cls.invoice.cfdi_required = False
        cls.invoice.action_post()

    def _render(self, report_ref, records):
        html, _report_type = self.env["ir.actions.report"]._render_qweb_html(
            report_ref, records.ids
        )
        return html.decode()

    def _stamp(self, invoice):
        cfdi = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "I",
                "issuer_id": self.issuer.id,
                "receiver_id": invoice.partner_id.id,
                "related_invoice_id": invoice.id,
                "serie": "TST",
                "folio": "1",
                "state": "published",
                "uuid": "11111111-2222-3333-4444-555555555555",
                "cert_data_json": STAMPED_CFDI_JSON,
            }
        )
        invoice.related_cert_ids = cfdi
        return cfdi

    def test_invoice_without_cfdi_has_no_cfdi_note(self):
        html = self._render("account.account_invoices", self.invoice)
        self.assertIn(self.invoice.name, html)
        self.assertNotIn(CFDI_NOTE, html)

    def test_invoice_with_cfdi_shows_cfdi_header_and_footer_note(self):
        self._stamp(self.invoice)
        html = self._render("account.account_invoices", self.invoice)
        self.assertIn(CFDI_NOTE, html)
        self.assertIn("Folio:", html)
        self.assertIn("TST", html)

    def test_invoice_with_cfdi_shows_the_sat_product_and_unit_columns(self):
        self._stamp(self.invoice)
        html = self._render("account.account_invoices", self.invoice)
        self.assertIn("Clave Prod. Serv.", html)
        self.assertIn("Clave Unidad", html)

    def test_invoice_without_payments_report_prints_the_cfdi_once(self):
        self._stamp(self.invoice)
        html = self._render("account.account_invoices_without_payment", self.invoice)
        self.assertEqual(html.count(CFDI_NOTE), 1)

    def test_payment_receipt_with_cfdi_shows_the_payment_cfdi(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 50.0,
                "journal_id": self.company_data["default_journal_bank"].id,
            }
        )
        cfdi = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "P",
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner_a.id,
                "related_payment_id": payment.id,
                "serie": "CP",
                "folio": "1",
                "state": "published",
                "uuid": "99999999-2222-3333-4444-555555555555",
                "cert_data_json": STAMPED_CFDI_JSON,
            }
        )
        payment.related_cert_ids = cfdi
        html = self._render("account.action_report_payment_receipt", payment)
        self.assertIn("Comprobante de Pago", html)
        self.assertIn(CFDI_NOTE, html)
