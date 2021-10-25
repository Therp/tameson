## Groups, menues and crons

### Groups

- (Debug on) Users > Select User > Technical settings > Pimcore to allow user full pimcore sync permission

### Menu

- Inventory > Configuration > Pimcore Config: Pimcore server configurations defined here
- Inventory > Configuration > Pimcore Response: List pimcore response objects here, can be used for view/monitoring purpose, manually import
- Inventory > Configuration > Pimcore Response Line: List pimcore response line objects here, can be used for view/monitoring purpose, canbe grouped by status, response no# etc.

### Cron

- Pimcore: Import data: run hourly, will import `draft` data from pimcore responses pulled and stored in odoo
- Pimcore: Pull data: run daily, will pull full Pimcore product database daily and store in a pimcore response object
- Pimcore: Pull data (New): run hourly, will pull new data only from pimcore server based on modification date comparison and store in a pimcore response object


## Data pulling

Two types of automated data pulling is implemented:
- Full data pulled from pimcore API, pulls all of the product data
- New data pulled from Pimcore based on modification date, only newer data is pulled

If existing SKU in Odoo, odoo cpmpares modification date of pulled data and existing SKU if pulled data has newer modification date, tries to update that products, if not skips
If not existing SKU in Odoo system, the new SKU pulled is imported as a new product in Odoo.

## Fields that will be updated with new modification time SKU
- 'name'
- 'pimcore_id'
- 'default_code'
- 'barcode'
- 'weight'
- 't_height'
- 't_length'
- 't_width'
- 'list_price'
- 'modification_date'
- 'hs_code'
- 'intrastat_id'
- 't_product_description_short'
- 't_use_up'
- 'standard_price'
- 't_use_up_replacement_sku'
- 'intrastat_origin_country_id'
- 't_customer_backorder_allowed'
- 't_customer_lead_time'
- 'brand_name'
- 'manufacturer_name'
- 'manufacturer_pn'
- 'oversized'
- 'imperial'
- 'non_returnable'
- Pricelists (USD/GBP)
- Translations
- Vendor info

## Data that will not updated with new modification time

- BOM
- Vendor price information

## Error checking
- Error are reported per line in pimcore response
- If errors are generated while updating a product from pimcore response line, it  will be marked as `error` state
- Lines are grouped by response id and state in pimcore response line menu, for easily check or filter.