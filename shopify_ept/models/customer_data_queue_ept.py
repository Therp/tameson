from odoo import api, fields, models


class ShopifyCustomerDataQueueEpt(models.Model):
    _name = "shopify.customer.data.queue.ept"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Shopify Synced Customer Data Ept"

    name = fields.Char(size=120, string="Name", readonly=True)
    shopify_instance_id = fields.Many2one("shopify.instance.ept", string="Instance")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("partially_completed", "Partially Completed"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        compute="_compute_queue_state",
        default="draft",
        store=True,
    )
    synced_customer_queue_line_ids = fields.One2many(
        "shopify.customer.data.queue.line.ept", "synced_customer_queue_id", "Customers"
    )
    total_record_count = fields.Integer(
        string="Total Records Count", compute="_compute_total_record_count"
    )
    draft_state_count = fields.Integer(
        string="Draft State Count", compute="_compute_total_record_count"
    )
    fail_state_count = fields.Integer(
        string="Fail State Count", compute="_compute_total_record_count"
    )
    done_state_count = fields.Integer(
        string="Done State Count", compute="_compute_total_record_count"
    )
    cancel_state_count = fields.Integer(
        string="Cancel State Count", compute="_compute_total_record_count"
    )
    common_log_book_id = fields.Many2one(
        "common.log.book.ept",
        string="Log Book",
        help="""Related Log book which has all logs for current queue.""",
    )
    common_log_lines_ids = fields.One2many(related="common_log_book_id.log_lines")
    record_created_from = fields.Selection(
        [("webhook", "From Webhook"), ("import_process", "From Import Process")],
        store=True,
    )
    is_process_queue = fields.Boolean("Is Processing Queue", default=False)
    running_status = fields.Char(default="Running...")
    is_action_require = fields.Boolean(default=False)
    queue_process_count = fields.Integer(
        string="Queue Process Times",
        help="it is used know queue how many time processed",
    )

    @api.depends("synced_customer_queue_line_ids.state")
    def _compute_total_record_count(self):
        """
        Change the queue and queue line record state using this compute method
        :param results:
        :return:
        :author: Angel Patel @Emipro Technologies Pvt.Ltd on date 02/11/2019.
        :Task ID: 157065
        :Modify by Haresh Mori on date 25/12/2019, optimize the code
        """
        for record in self:
            queue_lines = record.synced_customer_queue_line_ids
            record.total_record_count = len(queue_lines)
            record.draft_state_count = len(
                queue_lines.filtered(lambda x: x.state == "draft")
            )
            record.done_state_count = len(
                queue_lines.filtered(lambda x: x.state == "done")
            )
            record.fail_state_count = len(
                queue_lines.filtered(lambda x: x.state == "failed")
            )
            record.cancel_state_count = len(
                queue_lines.filtered(lambda x: x.state == "cancel")
            )

    @api.depends("synced_customer_queue_line_ids.state")
    def _compute_queue_state(self):
        """
        Computes state from different states of queue lines.
        @author: Haresh Mori on Date 25-Dec-2019.
        """
        for record in self:
            if (
                record.total_record_count
                == record.done_state_count + record.cancel_state_count
            ):
                record.state = "completed"
            elif record.draft_state_count == record.total_record_count:
                record.state = "draft"
            elif record.total_record_count == record.fail_state_count:
                record.state = "failed"
            else:
                record.state = "partially_completed"

    @api.model
    def create(self, vals):
        """This method used to create a sequence for synced shopify data.
        @param : self,vals
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 25/10/2019.
        :Task ID: 157065
        """
        seq = (
            self.env["ir.sequence"].next_by_code("shopify.customer.data.queue.ept")
            or "/"
        )
        vals.update({"name": seq or ""})
        return super(ShopifyCustomerDataQueueEpt, self).create(vals)

    @api.model
    def shopify_create_customer_queue(self, instance, record_created_from):
        """This method used to create a customer queue.
        @param : self, insatnce.
        @author: Angel Patel@Emipro Technologies Pvt. Ltd on date 08/1/2020.
        """
        customer_queue_vals = {
            "shopify_instance_id": instance and instance.id or False,
            "state": "draft",
            "record_created_from": record_created_from,
        }
        customer_queue_data_id = self.create(customer_queue_vals)

        return customer_queue_data_id
