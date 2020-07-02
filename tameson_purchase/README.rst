.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :target: https://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3

================
Tameson_purchase
================


Purchase customizations for Tameson

    * extends OCA procurement_no_grouping to skip grouping on select suppliers, 
      and mantain grouping on others, by setting a new grouping policy "line_specific", 
      and by setting
    * for all ungrouped PO lines adds a link to the origin SO, if any.
