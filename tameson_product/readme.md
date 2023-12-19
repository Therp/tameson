**src/tameson/tameson_product/data/cron.xml**

-   Tameson: Set Update Products BOM price
-   Tameson: Set all BOM price

**src/tameson/tameson_product/models/mrp_bom.py**

-   set_bom_price: calculate bom price from BOM
-   set_bom_sale_price_job: For using with cron to compute all sale price using job queue
-   set_bom_cost_price_job: For using with cron to compute all cost price using job queue

**src/tameson/tameson_product/models/product_template.py**

-   add unique sku db constraint
-   supplier info name, code, delay
-   Tameson product fields
-   AA packing size
-   Supplier info
-   updated boms price calc
-   Non bom lead calc
-   eur group margin

Tameson Product Customizations.

Includes additional Tameson specific fields added to products (Pimcore specific and other usage).

Also includes the computed stored fields for vendor name, vendor SKU and vendor delivery lead time (first vendor only if multiple are found).
