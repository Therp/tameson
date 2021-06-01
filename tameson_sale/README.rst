============
Tameson_sale
============


Sale related customizations for Tameson

    * Includes fields to enable invoice control policy (ordered/delivered)
      on sale order/sale order lines/payment terms (over-riding the product).
    * Adds a field to mark the order as paid.
    * Runs periodic checks to make sure the business logic is correct and
      a cron job to send notifications when it finds non-validated invoices
      for done pickings.
    * Add credit_limit fields visible for parent contact, for users of group
      Sale administrator/Accounting advisors
    * Add credit checking based on open invoice, open orders without invoice,
      block order confirmation if credit_limit is crossed. can be bypassed using
      credit limit bypass bool field on sale order for users of group
      Sale administrator/Accounting advisors
